"""Email alerts for user reports that suggest imminent conflict risk."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
import logging
import re

from agents import Agent, OpenAIChatCompletionsModel, Runner
import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

RESEND_SEND_URL = "https://api.resend.com/emails"
TWILIO_MESSAGES_URL_TEMPLATE = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
PUSHOVER_MESSAGES_URL = "https://api.pushover.net/1/messages.json"
CONFLICT_ALERT_SENDER = "Ubuntu Voice <onboarding@resend.dev>"

_CONFLICT_KEYWORDS = (
    "war",
    "armed conflict",
    "fighting",
    "violence",
    "attack",
    "militia",
    "armed men",
    "armed group",
    "clashes",
    "riot",
    "unrest",
    "massacre",
)
_IMMINENCE_KEYWORDS = (
    "about to",
    "imminent",
    "soon",
    "tonight",
    "tomorrow",
    "breaking out",
    "break out",
    "planned",
    "preparing",
    "mobilizing",
    "gathering",
    "threatened",
    "threatening",
)

_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{6,}\d)(?!\w)")
_NAME_RE = re.compile(
    r"\b(my name is|this is)\s+[A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,3}",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ConflictAlert:
    """Sanitized alert email content prepared for a registered agent contact."""

    subject: str
    body: str


class ConflictAlertDecision(BaseModel):
    """Structured output from the alert-decision agent."""

    send_alert: bool = Field(
        ...,
        description="True only when the user prompt describes an emergency requiring an alert email.",
    )


class ConflictAlertDraft(BaseModel):
    """Structured output from the alert-drafting agent."""

    subject: str = Field(..., min_length=1, max_length=120)
    issue_summary: str = Field(..., min_length=1, max_length=500)


def should_send_conflict_alert(message: str) -> bool:
    """Return true when a message appears to report near-term conflict risk."""
    normalized = message.lower()
    has_conflict_signal = any(keyword in normalized for keyword in _CONFLICT_KEYWORDS)
    has_imminence_signal = any(keyword in normalized for keyword in _IMMINENCE_KEYWORDS)
    return has_conflict_signal and has_imminence_signal


def redact_personal_contact_details(text: str) -> str:
    """Remove obvious user emails, phone numbers, and self-declared names."""
    redacted = _EMAIL_RE.sub("[redacted email]", text)
    redacted = _PHONE_RE.sub("[redacted phone]", redacted)
    redacted = _NAME_RE.sub(r"\1 [redacted name]", redacted)
    return redacted.strip()


def build_conflict_alert_from_draft(
    *,
    company_name: str,
    detected_at: str,
    draft: ConflictAlertDraft,
) -> ConflictAlert:
    """Build the final minimal alert email body from an agent-generated draft."""
    body = "\n".join(
        [
            f"Agent: {company_name}",
            f"Detected at: {detected_at}",
            f"Summary: {draft.issue_summary}",
        ]
    )
    return ConflictAlert(subject=draft.subject, body=body)


async def decide_conflict_alert(
    *,
    async_client: AsyncOpenAI,
    chat_model: str,
    user_message: str,
) -> ConflictAlertDecision:
    """Use an agent with structured output to decide whether an alert is needed."""
    model = OpenAIChatCompletionsModel(model=chat_model, openai_client=async_client)
    decision_agent = Agent(
        name="Conflict Alert Decision Agent",
        instructions=(
            "Use the user prompt to determine whether there is an emergency issue such as conflict about "
            "to break out, casualties left unattended, ongoing conflict, active violence, armed actors, "
            "or imminent harm. Return send_alert=true only when an alert email should be sent. "
            "Return send_alert=false for greetings, general questions, historical questions, or non-urgent support requests."
        ),
        model=model,
        output_type=ConflictAlertDecision,
    )
    result = await Runner.run(
        decision_agent,
        f"User prompt:\n{redact_personal_contact_details(user_message)}",
        max_turns=2,
    )
    return result.final_output_as(ConflictAlertDecision)


async def draft_conflict_alert(
    *,
    async_client: AsyncOpenAI,
    chat_model: str,
    company_name: str,
    detected_at: str,
    user_message: str,
) -> ConflictAlertDraft:
    """Use an agent with structured output to draft a concise alert email."""
    model = OpenAIChatCompletionsModel(model=chat_model, openai_client=async_client)
    draft_agent = Agent(
        name="Conflict Alert Draft Agent",
        instructions=(
            "The user prompt indicates an emergency that needs an alert. Write a clear, professional "
            "email subject and a short issue summary based only on the sanitized user prompt. "
            "Do not include user names, phone numbers, emails, account IDs, or unsupported instructions. "
            "Keep the issue summary factual and concise."
        ),
        model=model,
        output_type=ConflictAlertDraft,
    )
    result = await Runner.run(
        draft_agent,
        "\n".join(
            [
                f"Agent name: {company_name}",
                f"Detected at: {detected_at}",
                f"Sanitized user prompt: {redact_personal_contact_details(user_message)}",
            ]
        ),
        max_turns=2,
    )
    return result.final_output_as(ConflictAlertDraft)


async def send_conflict_alert_email(
    *,
    resend_api_key: str,
    recipient_email: str,
    alert: ConflictAlert,
) -> None:
    """Send a conflict alert through Resend's email API."""
    payload = {
        "from": CONFLICT_ALERT_SENDER,
        "to": [recipient_email],
        "subject": alert.subject,
        "html": escape(alert.body).replace("\n", "<br>"),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            RESEND_SEND_URL,
            headers={
                "Authorization": f"Bearer {resend_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    response.raise_for_status()


async def send_conflict_alert_sms(
    *,
    twilio_account_sid: str,
    twilio_auth_token: str,
    from_number: str,
    to_number: str,
    alert: ConflictAlert,
) -> None:
    """Send a concise conflict alert SMS through Twilio's Messages REST API."""
    body = f"{alert.subject}\n{alert.body}"
    url = TWILIO_MESSAGES_URL_TEMPLATE.format(account_sid=twilio_account_sid)
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,
            data={"From": from_number, "To": to_number, "Body": body},
            auth=(twilio_account_sid, twilio_auth_token),
        )
    response.raise_for_status()


async def send_conflict_alert_push(
    *,
    pushover_user: str,
    pushover_token: str,
    alert: ConflictAlert,
) -> None:
    """Send a concise conflict-alert push notification through Pushover."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            PUSHOVER_MESSAGES_URL,
            data={
                "user": pushover_user,
                "token": pushover_token,
                "message": f"{alert.subject}\n{alert.body}",
            },
        )
    response.raise_for_status()


async def maybe_send_conflict_alert(
    *,
    async_client: AsyncOpenAI,
    chat_model: str,
    resend_api_key: str | None,
    company_id: str,
    company_name: str,
    recipient_email: str,
    user_message: str,
    language: str,
    twilio_account_sid: str | None = None,
    twilio_auth_token: str | None = None,
    twilio_sms_from_number: str | None = None,
    twilio_sms_to_number: str | None = None,
    pushover_user: str | None = None,
    pushover_token: str | None = None,
) -> bool:
    """Use alert agents to decide, draft, and send alert email plus optional SMS/push."""
    try:
        decision = await decide_conflict_alert(
            async_client=async_client,
            chat_model=chat_model,
            user_message=user_message,
        )
    except Exception as exc:  # noqa: BLE001 - alert failure must not break chat
        logger.warning(
            "Conflict alert decision failed: company_id=%s error=%s",
            company_id,
            exc.__class__.__name__,
        )
        return False

    if not decision.send_alert:
        logger.info("Conflict alert decision: no email needed for company_id=%s", company_id)
        return False

    if not resend_api_key:
        logger.warning(
            "Conflict alert detected but RESEND_API_KEY is not configured: company_id=%s",
            company_id,
        )
        return False

    detected_at = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        draft = await draft_conflict_alert(
            async_client=async_client,
            chat_model=chat_model,
            company_name=company_name,
            detected_at=detected_at,
            user_message=user_message,
        )
    except Exception as exc:  # noqa: BLE001 - alert failure must not break chat
        logger.warning(
            "Conflict alert draft failed: company_id=%s error=%s",
            company_id,
            exc.__class__.__name__,
        )
        return False

    alert = build_conflict_alert_from_draft(
        company_name=company_name,
        detected_at=detected_at,
        draft=draft,
    )
    email_task = asyncio.create_task(
        send_conflict_alert_email(
            resend_api_key=resend_api_key,
            recipient_email=recipient_email,
            alert=alert,
        )
    )
    sms_task = None
    if all(
        [
            twilio_account_sid,
            twilio_auth_token,
            twilio_sms_from_number,
            twilio_sms_to_number,
        ]
    ):
        sms_task = asyncio.create_task(
            send_conflict_alert_sms(
                twilio_account_sid=twilio_account_sid,
                twilio_auth_token=twilio_auth_token,
                from_number=twilio_sms_from_number,
                to_number=twilio_sms_to_number,
                alert=alert,
            )
        )
    else:
        logger.info("Conflict alert SMS skipped because Twilio SMS settings are incomplete: company_id=%s", company_id)

    push_task = None
    if pushover_user and pushover_token:
        push_task = asyncio.create_task(
            send_conflict_alert_push(
                pushover_user=pushover_user,
                pushover_token=pushover_token,
                alert=alert,
            )
        )
    else:
        logger.info("Conflict alert push skipped because Pushover settings are incomplete: company_id=%s", company_id)

    results = await asyncio.gather(
        *(task for task in (email_task, sms_task, push_task) if task is not None),
        return_exceptions=True,
    )
    email_result = results[0]
    if isinstance(email_result, Exception):
        logger.warning(
            "Conflict alert email failed: company_id=%s status_error=%s",
            company_id,
            email_result.__class__.__name__,
        )
        return False

    if sms_task is not None and len(results) > 1:
        sms_result = results[1]
        if isinstance(sms_result, Exception):
            logger.warning(
                "Conflict alert SMS failed: company_id=%s status_error=%s",
                company_id,
                sms_result.__class__.__name__,
            )
        else:
            logger.info("Conflict alert SMS sent: company_id=%s", company_id)

    if push_task is not None:
        push_result = results[-1]
        if isinstance(push_result, Exception):
            logger.warning(
                "Conflict alert push failed: company_id=%s status_error=%s",
                company_id,
                push_result.__class__.__name__,
            )
        else:
            logger.info("Conflict alert push sent: company_id=%s", company_id)

    logger.info("Conflict alert email sent: company_id=%s", company_id)
    return True
