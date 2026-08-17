"""HTTP routes for the RAG-grounded customer support agent."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from src.api.v1.schemas.agent import AgentChatRequest, AgentChatResponse
from src.core.auth import UserIdentity, get_authenticated_user_identity, get_optional_auth_session, require_auth_session
from src.core.config import Settings
from src.core.dependencies import get_db_session, get_openrouter_client, get_settings
from src.services.cost_monitoring import merge_usage_charges, record_user_spend
from src.services.guardrails import (
    evaluate_input,
    evaluate_output,
    record_guardrail_event,
)
from src.services.incident_statistics import IncidentLocation, classify_and_store_incident_statistics
from src.models import Company
from src.services.ingestion import upsert_user
from src.services.conflict_alerts import maybe_send_conflict_alert
from src.services.rag_agent import run_rag_agent

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("/chat", response_model=AgentChatResponse)
async def post_agent_chat(
    body: AgentChatRequest,
    session_state: Annotated[UserIdentity | None, Depends(get_optional_auth_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[AsyncOpenAI, Depends(get_openrouter_client)],
    db_session: Annotated[Session, Depends(get_db_session)],
    background_tasks: BackgroundTasks,
) -> AgentChatResponse:
    """Run the two-phase RAG agent pipeline for a publicly selectable agent.

    Phase 1: A prompt prepares the latest message for retrieval using recent
    history, skipping retrieval for general conversation. Phase 2: the answer
    agent receives the current message, history, retrieval status, and any
    trusted excerpts before producing the final reply.

    Any visitor may chat with an available agent. Authentication is used only
    for optional usage and safety-event attribution; it does not restrict the
    agent corpus a visitor can select. Returns HTTP 404 when the agent does
    not exist.
    """
    user = None
    if session_state is not None:
        identity = get_authenticated_user_identity(session_state)
        user, _created = upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    company = db_session.query(Company).filter(Company.id == body.company_id).one_or_none()
    if company is None or not company.is_approved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    db_session.commit()

    input_check = evaluate_input(
        message=body.message,
        max_tokens=settings.guardrail_max_input_tokens,
        encoding_name=settings.guardrail_token_encoding,
    )
    if not input_check.allowed:
        if user is not None:
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

    background_tasks.add_task(
        classify_and_store_incident_statistics,
        database_url=settings.database_url,
        openrouter_api_key=settings.openrouter_api_key,
        openrouter_base_url=settings.openrouter_base_url,
        chat_model=settings.openrouter_model,
        company_id=company.id,
        user_prompt=body.message,
        location=(IncidentLocation.model_validate(body.location.model_dump()) if body.location is not None else None),
    )

    # Alerts belong to the selected agent, not to the identity of the person
    # reporting the emergency. Public chat may be used by anonymous visitors
    # and by users who do not own the selected agent.
    await maybe_send_conflict_alert(
        async_client=client,
        chat_model=settings.openrouter_model,
        sendgrid_api_key=settings.sendgrid_api_key,
        sendgrid_from_email=settings.sendgrid_from_email,
        twilio_account_sid=settings.twilio_account_sid,
        twilio_auth_token=settings.twilio_auth_token,
        twilio_sms_from_number=settings.twilio_sms_from_number,
        twilio_sms_to_number=settings.twilio_sms_to_number,
        pushover_user=settings.pushover_user,
        pushover_token=settings.pushover_token,
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
        history=[turn.model_dump() for turn in body.history],
        language=body.language,
        chat_model=settings.openrouter_model,
        embedding_model=settings.embedding_model,
        embedding_dimensions=settings.embedding_dimensions,
        top_k=settings.rag_top_k,
        similarity_threshold=settings.rag_similarity_threshold,
        openrouter_api_key=settings.openrouter_api_key,
        openrouter_base_url=settings.openrouter_base_url,
    )
    if usage_charges and user is not None:
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
    if output_check.triggered and user is not None:
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
