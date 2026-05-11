"""HTTP routes for the RAG-grounded customer support agent."""

from typing import Annotated

from clerk_backend_api.security.types import RequestState
from fastapi import APIRouter, Depends, HTTPException, status
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from src.api.v1.schemas.agent import AgentChatRequest, AgentChatResponse
from src.core.clerk_auth import get_authenticated_user_identity, require_clerk_session
from src.core.config import Settings
from src.core.dependencies import get_db_session, get_openrouter_client, get_settings
from src.services.cost_monitoring import merge_usage_charges, record_user_spend
from src.services.guardrails import (
    evaluate_input,
    evaluate_output,
    record_guardrail_event,
)
from src.services.ingestion import get_owned_company, upsert_user
from src.services.conflict_alerts import maybe_send_conflict_alert
from src.services.rag_agent import run_rag_agent

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/chat", response_model=AgentChatResponse)
async def post_agent_chat(
    body: AgentChatRequest,
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[AsyncOpenAI, Depends(get_openrouter_client)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> AgentChatResponse:
    """Run the two-phase RAG agent pipeline for the authenticated owner's company.

    Phase 1: A retrieval agent calls the ``search_knowledge_base`` tool which
    embeds the user's question and queries pgvector for the tenant's chunks.
    Phase 2: An answer agent receives the verified context and produces the
    final customer-facing reply. Both phases run inside a single trace.

    Returns HTTP 404 when the company_id is not found or does not belong to
    the authenticated user.
    """
    identity = get_authenticated_user_identity(session_state)
    user, _created = upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    company = get_owned_company(db_session, company_id=body.company_id, owner_id=user.id)
    db_session.commit()

    input_check = evaluate_input(
        message=body.message,
        max_tokens=settings.guardrail_max_input_tokens,
        encoding_name=settings.guardrail_token_encoding,
    )
    if not input_check.allowed:
        record_guardrail_event(
            db_session,
            user_id=user.id,
            company_id=company.id,
            event_type="input_token_limit",
            action="blocked",
            matched_rules=["token_limit"],
            prompt_text=body.message,
            response_text=None,
            input_token_count=input_check.token_count,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=input_check.reason,
        )

    await maybe_send_conflict_alert(
        async_client=client,
        chat_model=settings.openrouter_model,
        sendgrid_api_key=settings.sendgrid_api_key,
        company_id=company.id,
        company_name=company.name,
        recipient_email=company.email,
        user_message=body.message,
        language=body.language,
    )

    reply, grounded, usage_charges = await run_rag_agent(
        async_client=client,
        db_session=db_session,
        company_id=company.id,
        company_name=company.name,
        user_message=body.message,
        language=body.language,
        chat_model=settings.openrouter_model,
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
        top_k=settings.rag_top_k,
        similarity_threshold=settings.rag_similarity_threshold,
        openrouter_api_key=settings.openrouter_api_key,
        openrouter_base_url=settings.openrouter_base_url,
    )
    if usage_charges:
        record_user_spend(
            db_session,
            user_id=user.id,
            email=user.email,
            charge=merge_usage_charges(usage_charges),
        )
        db_session.commit()

    output_check = evaluate_output(
        reply=reply,
        phone_country_code=settings.guardrail_phone_country_code,
    )
    if output_check.triggered:
        record_guardrail_event(
            db_session,
            user_id=user.id,
            company_id=company.id,
            event_type="output_pii",
            action="monitored",
            matched_rules=output_check.matched_rules,
            prompt_text=body.message,
            response_text=reply,
            input_token_count=input_check.token_count,
        )

    return AgentChatResponse(reply=reply, grounded=grounded)
