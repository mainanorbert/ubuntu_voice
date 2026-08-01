"""WhatsApp channel helpers for Twilio webhook parsing, routing, and replies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import re

import httpx
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.models import Company, WhatsAppAgentSession, generate_uuid

TWILIO_MESSAGES_URL_TEMPLATE = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
WHATSAPP_MENU_COMMANDS = frozenset({"agent", "agents", "menu", "switch"})


class WhatsAppConfigurationError(RuntimeError):
    """Raised when required Twilio settings are missing for sending replies."""


class WhatsAppDeliveryError(RuntimeError):
    """Raised when Twilio rejects or cannot receive an outbound WhatsApp reply."""


@dataclass(frozen=True)
class TwilioWhatsAppMessage:
    """Parsed inbound Twilio WhatsApp webhook fields."""

    body: str
    from_number: str
    to_number: str | None
    message_sid: str | None


def _form_value(form: Mapping[str, object], key: str) -> str | None:
    """Return a stripped string value from Twilio form data."""
    value = form.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_twilio_whatsapp_message(form: Mapping[str, object]) -> TwilioWhatsAppMessage:
    """Extract the minimal inbound message fields from Twilio form data."""
    return TwilioWhatsAppMessage(
        body=_form_value(form, "Body") or "",
        from_number=_form_value(form, "From") or "",
        to_number=_form_value(form, "To"),
        message_sid=_form_value(form, "MessageSid"),
    )


def normalize_whatsapp_phone_number(value: str | None) -> str | None:
    """Normalize Twilio WhatsApp addresses to bare E.164 phone strings."""
    if not value:
        return None
    raw = value.strip().lower()
    if raw.startswith("whatsapp:"):
        raw = raw.removeprefix("whatsapp:").strip()
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    return f"+{digits}"


def format_twilio_whatsapp_address(value: str) -> str:
    """Return a Twilio REST API WhatsApp address from a Twilio or bare phone value."""
    normalized = normalize_whatsapp_phone_number(value)
    if normalized is None:
        raise WhatsAppConfigurationError("Invalid WhatsApp phone address.")
    return f"whatsapp:{normalized}"


def build_whatsapp_participant_hash(*, phone_number: str, secret: str) -> str:
    """Derive a stable participant identifier without storing the user's phone number."""
    normalized = normalize_whatsapp_phone_number(phone_number)
    if normalized is None or not secret:
        raise WhatsAppConfigurationError("WhatsApp session identity cannot be derived.")
    return hmac.new(secret.encode("utf-8"), normalized.encode("utf-8"), hashlib.sha256).hexdigest()


def list_whatsapp_agents(db_session: Session) -> list[Company]:
    """List all currently registered agents in stable menu order."""
    return db_session.query(Company).order_by(Company.created_at.asc(), Company.id.asc()).all()


def format_whatsapp_agent_menu(companies: list[Company], *, invalid_selection: bool = False) -> str:
    """Build the numbered agent menu shown before a routing session is selected."""
    if not companies:
        return "No agents are currently available. Please try again later."

    heading = "That selection is not available.\n\n" if invalid_selection else ""
    options = "\n".join(f"{index}. {company.name}" for index, company in enumerate(companies, start=1))
    return (
        f"{heading}Welcome to Ubuntu Voice. Choose an agent:\n\n"
        f"{options}\n\nReply with the number of the agent you want to chat with."
    )


def parse_whatsapp_agent_selection(message: str, companies: list[Company]) -> Company | None:
    """Resolve a one-based numeric menu response to the corresponding agent."""
    selection = message.strip()
    if not re.fullmatch(r"\d+", selection):
        return None
    index = int(selection) - 1
    if index < 0 or index >= len(companies):
        return None
    return companies[index]


def is_whatsapp_menu_command(message: str) -> bool:
    """Return whether a participant explicitly requested the agent menu."""
    return message.strip().lower() in WHATSAPP_MENU_COMMANDS


def get_whatsapp_agent_session(
    db_session: Session,
    *,
    recipient_number: str,
    participant_hash: str,
    timeout_minutes: int,
    now: datetime | None = None,
) -> WhatsAppAgentSession | None:
    """Return an unexpired routing session, deleting it when inactivity has expired."""
    session = (
        db_session.query(WhatsAppAgentSession)
        .filter(
            WhatsAppAgentSession.recipient_number == recipient_number,
            WhatsAppAgentSession.participant_hash == participant_hash,
        )
        .one_or_none()
    )
    if session is None:
        return None

    current_time = now or datetime.now(timezone.utc)
    last_activity = session.last_activity_at
    if last_activity.tzinfo is None:
        last_activity = last_activity.replace(tzinfo=timezone.utc)
    if last_activity <= current_time - timedelta(minutes=timeout_minutes):
        db_session.delete(session)
        db_session.flush()
        return None
    return session


def upsert_whatsapp_agent_session(
    db_session: Session,
    *,
    recipient_number: str,
    participant_hash: str,
    company_id: str | None,
    now: datetime | None = None,
) -> None:
    """Atomically create or update a participant's menu or selected-agent state."""
    current_time = now or datetime.now(timezone.utc)
    values = {
        "id": generate_uuid(),
        "recipient_number": recipient_number,
        "participant_hash": participant_hash,
        "company_id": company_id,
        "last_activity_at": current_time,
    }
    conflict_columns = ["recipient_number", "participant_hash"]
    update_values = {"company_id": company_id, "last_activity_at": current_time}
    dialect_name = db_session.get_bind().dialect.name

    if dialect_name == "postgresql":
        statement = postgresql_insert(WhatsAppAgentSession).values(**values)
        statement = statement.on_conflict_do_update(index_elements=conflict_columns, set_=update_values)
        db_session.execute(statement)
    elif dialect_name == "sqlite":
        statement = sqlite_insert(WhatsAppAgentSession).values(**values)
        statement = statement.on_conflict_do_update(index_elements=conflict_columns, set_=update_values)
        db_session.execute(statement)
    else:
        existing = (
            db_session.query(WhatsAppAgentSession)
            .filter(
                WhatsAppAgentSession.recipient_number == recipient_number,
                WhatsAppAgentSession.participant_hash == participant_hash,
            )
            .one_or_none()
        )
        if existing is None:
            db_session.add(WhatsAppAgentSession(**values))
        else:
            existing.company_id = company_id
            existing.last_activity_at = current_time

    db_session.flush()


async def send_twilio_whatsapp_reply(
    *,
    settings: Settings,
    from_number: str,
    to_number: str,
    body: str,
) -> None:
    """Send a WhatsApp reply through Twilio's Messages REST API."""
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        raise WhatsAppConfigurationError("Twilio account credentials are not configured.")

    sender = format_twilio_whatsapp_address(from_number)
    recipient = format_twilio_whatsapp_address(to_number)
    url = TWILIO_MESSAGES_URL_TEMPLATE.format(account_sid=settings.twilio_account_sid)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                data={"From": sender, "To": recipient, "Body": body},
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise WhatsAppDeliveryError("Twilio WhatsApp delivery failed.") from exc
