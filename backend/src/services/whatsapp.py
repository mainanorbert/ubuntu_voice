"""WhatsApp channel helpers for Twilio webhook parsing, routing, and replies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re

import httpx
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.models import Company

TWILIO_MESSAGES_URL_TEMPLATE = "https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"


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


def resolve_company_by_whatsapp_number(
    db_session: Session,
    *,
    twilio_to_number: str | None,
    fallback_sender_number: str | None,
) -> Company | None:
    """Find the single agent assigned to the inbound Twilio recipient number."""
    normalized_target = normalize_whatsapp_phone_number(twilio_to_number) or normalize_whatsapp_phone_number(
        fallback_sender_number
    )
    if normalized_target is None:
        return None

    exact_matches = db_session.query(Company).filter(Company.phone == normalized_target).all()
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        return None

    companies_with_phone = db_session.query(Company).filter(Company.phone.isnot(None)).all()
    normalized_matches = [
        company
        for company in companies_with_phone
        if normalize_whatsapp_phone_number(company.phone) == normalized_target
    ]
    if len(normalized_matches) == 1:
        return normalized_matches[0]
    return None


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
