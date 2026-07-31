"""External channel webhooks."""

from datetime import datetime, timezone
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import PlainTextResponse
from openai import AsyncOpenAI
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.core.dependencies import get_db_session, get_openrouter_client, get_settings
from src.models import Company, User
from src.services.conflict_alerts import maybe_send_conflict_alert
from src.services.cost_monitoring import merge_usage_charges, record_user_spend
from src.services.guardrails import evaluate_input, evaluate_output, record_guardrail_event
from src.services.incident_statistics import classify_and_store_incident_statistics
from src.services.rag_agent import run_rag_agent
from src.services.whatsapp import (
    WhatsAppConfigurationError,
    WhatsAppDeliveryError,
    build_whatsapp_participant_hash,
    format_whatsapp_agent_menu,
    get_whatsapp_agent_session,
    is_whatsapp_menu_command,
    list_whatsapp_agents,
    normalize_whatsapp_phone_number,
    parse_twilio_whatsapp_message,
    parse_whatsapp_agent_selection,
    send_twilio_whatsapp_reply,
    upsert_whatsapp_agent_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
legacy_router = APIRouter(tags=["webhooks"])

WHATSAPP_FALLBACK_REPLY = "Sorry, I'm having trouble processing that right now. Please try again shortly."
WHATSAPP_ACK_RESPONSE = PlainTextResponse("")


async def build_whatsapp_agent_reply(
    *,
    settings: Settings,
    client: AsyncOpenAI,
    db_session: Session,
    company: Company,
    user_message: str,
    background_tasks: BackgroundTasks,
) -> str:
    """Run one WhatsApp message through the matched agent's existing chat pipeline."""
    owner = db_session.get(User, company.owner_id)
    input_check = evaluate_input(
        message=user_message,
        max_tokens=settings.guardrail_max_input_tokens,
        encoding_name=settings.guardrail_token_encoding,
    )
    if not input_check.allowed:
        record_guardrail_event(
            db_session,
            user_id=company.owner_id,
            company_id=company.id,
            event_type="input_token_limit",
            action="blocked",
            matched_rules=["token_limit"],
            prompt_text=user_message,
            response_text=None,
            input_token_count=input_check.token_count,
        )
        return input_check.reason or "Please send a shorter, focused message."

    background_tasks.add_task(
        classify_and_store_incident_statistics,
        database_url=settings.database_url,
        openrouter_api_key=settings.openrouter_api_key,
        openrouter_base_url=settings.openrouter_base_url,
        chat_model=settings.openrouter_model,
        company_id=company.id,
        user_prompt=user_message,
    )

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
        user_message=user_message,
        language="English",
    )

    reply, _grounded, usage_charges = await run_rag_agent(
        async_client=client,
        db_session=db_session,
        company_id=company.id,
        company_name=company.name,
        user_message=user_message,
        language="English",
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
            user_id=company.owner_id,
            email=owner.email if owner is not None else None,
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
            user_id=company.owner_id,
            company_id=company.id,
            event_type="output_pii",
            action="monitored",
            matched_rules=output_check.matched_rules,
            prompt_text=user_message,
            response_text=reply,
            input_token_count=input_check.token_count,
        )

    return reply


async def handle_twilio_whatsapp_webhook(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    client: Annotated[AsyncOpenAI, Depends(get_openrouter_client)],
    db_session: Annotated[Session, Depends(get_db_session)],
    background_tasks: BackgroundTasks,
) -> PlainTextResponse:
    """Route a Twilio WhatsApp participant through agent selection and an expiring session."""
    form = await request.form()
    inbound = parse_twilio_whatsapp_message(form)
    if not inbound.body or not inbound.from_number:
        return WHATSAPP_ACK_RESPONSE

    sender_number = inbound.to_number or settings.twilio_whatsapp_number
    recipient_number = normalize_whatsapp_phone_number(sender_number)
    configured_recipient_number = normalize_whatsapp_phone_number(settings.twilio_whatsapp_number)
    session_secret = settings.whatsapp_session_secret or settings.twilio_auth_token
    if (
        sender_number is None
        or recipient_number is None
        or configured_recipient_number is None
        or recipient_number != configured_recipient_number
        or session_secret is None
    ):
        logger.warning("Ignoring WhatsApp webhook because session routing is not configured.")
        return WHATSAPP_ACK_RESPONSE

    try:
        participant_hash = build_whatsapp_participant_hash(
            phone_number=inbound.from_number,
            secret=session_secret,
        )
    except WhatsAppConfigurationError:
        logger.warning("Ignoring WhatsApp webhook because the participant identifier was invalid.")
        return WHATSAPP_ACK_RESPONSE

    whatsapp_session = get_whatsapp_agent_session(
        db_session,
        recipient_number=recipient_number,
        participant_hash=participant_hash,
        timeout_minutes=settings.whatsapp_session_timeout_minutes,
    )

    company: Company | None = None
    if whatsapp_session is None:
        companies = list_whatsapp_agents(db_session)
        upsert_whatsapp_agent_session(
            db_session,
            recipient_number=recipient_number,
            participant_hash=participant_hash,
            company_id=None,
        )
        db_session.commit()
        reply = format_whatsapp_agent_menu(companies)
    elif whatsapp_session.company_id is None:
        companies = list_whatsapp_agents(db_session)
        selected_company = parse_whatsapp_agent_selection(inbound.body, companies)
        if selected_company is None:
            reply = format_whatsapp_agent_menu(
                companies,
                invalid_selection=inbound.body.strip().isdigit(),
            )
            db_session.commit()
        else:
            upsert_whatsapp_agent_session(
                db_session,
                recipient_number=recipient_number,
                participant_hash=participant_hash,
                company_id=selected_company.id,
            )
            db_session.commit()
            reply = (
                f"You are now chatting with {selected_company.name}. "
                "Send your question, or reply MENU to choose another agent."
            )
    elif is_whatsapp_menu_command(inbound.body):
        companies = list_whatsapp_agents(db_session)
        whatsapp_session.company_id = None
        whatsapp_session.last_activity_at = datetime.now(timezone.utc)
        db_session.commit()
        reply = format_whatsapp_agent_menu(companies)
    else:
        company = db_session.get(Company, whatsapp_session.company_id)
        if company is None:
            companies = list_whatsapp_agents(db_session)
            whatsapp_session.company_id = None
            whatsapp_session.last_activity_at = datetime.now(timezone.utc)
            db_session.commit()
            reply = format_whatsapp_agent_menu(companies)
        else:
            whatsapp_session.last_activity_at = datetime.now(timezone.utc)
            db_session.commit()

    if company is not None:
        try:
            reply = await build_whatsapp_agent_reply(
                settings=settings,
                client=client,
                db_session=db_session,
                company=company,
                user_message=inbound.body,
                background_tasks=background_tasks,
            )
        except Exception as exc:  # noqa: BLE001 - WhatsApp should receive a graceful fallback.
            logger.exception(
                "WhatsApp agent reply failed: company_id=%s error=%s",
                company.id,
                exc.__class__.__name__,
            )
            reply = WHATSAPP_FALLBACK_REPLY

    try:
        await send_twilio_whatsapp_reply(
            settings=settings,
            from_number=sender_number,
            to_number=inbound.from_number,
            body=reply,
        )
    except (WhatsAppConfigurationError, WhatsAppDeliveryError) as exc:
        logger.warning(
            "WhatsApp reply delivery failed: company_id=%s error=%s",
            company.id if company is not None else None,
            exc.__class__.__name__,
        )

    return WHATSAPP_ACK_RESPONSE


router.add_api_route("/whatsapp/twilio", handle_twilio_whatsapp_webhook, methods=["POST"])
legacy_router.add_api_route(
    "/whatsapp-webhook",
    handle_twilio_whatsapp_webhook,
    methods=["POST"],
    include_in_schema=False,
)
