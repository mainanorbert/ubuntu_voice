"""Tests for emerging-conflict email alert detection and redaction."""

import asyncio

from sendgrid.helpers.mail import Mail

from src.services import conflict_alerts
from src.services.conflict_alerts import (
    ConflictAlert,
    ConflictAlertDecision,
    ConflictAlertDraft,
    build_conflict_alert_from_draft,
    maybe_send_conflict_alert,
    redact_personal_contact_details,
    send_conflict_alert_email,
    should_send_conflict_alert,
)


def test_should_send_conflict_alert_for_imminent_war_report() -> None:
    """Imminent conflict reports are detected before normal RAG handling."""
    assert should_send_conflict_alert("There is a war which is about to break out in city X.")


def test_should_not_send_conflict_alert_for_general_history_question() -> None:
    """General conflict-related questions without imminent risk do not alert."""
    assert not should_send_conflict_alert("What does the document say about war recovery programs?")


def test_conflict_alert_body_redacts_user_contact_details() -> None:
    """Alert bodies retain incident details while removing obvious user PII."""
    message = (
        "My name is Jane Doe. There is violence about to break out in City X. "
        "Call me on +254 712-345-678 or jane@example.org."
    )

    body = build_conflict_alert_from_draft(
        company_name="Sahel Peace Mediator",
        detected_at="2026-05-11T12:00:00+00:00",
        draft=ConflictAlertDraft(
            subject="Potential conflict alert",
            issue_summary=redact_personal_contact_details(message),
        ),
    ).body

    assert "City X" in body
    assert "Jane Doe" not in body
    assert "+254 712-345-678" not in body
    assert "jane@example.org" not in body
    assert "[redacted name]" in body
    assert "[redacted phone]" in body
    assert "[redacted email]" in body


def test_redact_personal_contact_details_preserves_location_context() -> None:
    """Redaction avoids stripping useful place details from an alert."""
    redacted = redact_personal_contact_details("War is about to break out near City X market.")
    assert redacted == "War is about to break out near City X market."


def test_send_conflict_alert_email_uses_sendgrid_message(monkeypatch) -> None:
    """SendGrid receives the configured sender, company email, and HTML body."""
    calls: list[dict] = []

    class FakeResponse:
        """Minimal SendGrid response stub for successful delivery."""

        status_code = 202

    class FakeSendGridClient:
        """Capture outbound SendGrid requests without making network calls."""

        def __init__(self, api_key: str) -> None:
            calls.append({"api_key": api_key})

        def send(self, message: Mail) -> FakeResponse:
            calls[0]["message"] = message.get()
            return FakeResponse()

    monkeypatch.setattr(conflict_alerts, "SendGridAPIClient", FakeSendGridClient)

    async def run_in_place(callback):
        return callback()

    monkeypatch.setattr(conflict_alerts.asyncio, "to_thread", run_in_place)

    asyncio.run(
        send_conflict_alert_email(
            sendgrid_api_key="test-key",
            sender_email="alerts@example.org",
            recipient_email="agent-contact@example.org",
            alert=ConflictAlert(subject="Urgent report", body="Line one\nLine two"),
        )
    )

    assert calls[0]["api_key"] == "test-key"
    assert calls[0]["message"]["from"] == {"email": "alerts@example.org"}
    assert calls[0]["message"]["personalizations"][0]["to"] == [{"email": "agent-contact@example.org"}]
    assert calls[0]["message"]["subject"] == "Urgent report"
    assert calls[0]["message"]["content"] == [{"type": "text/html", "value": "Line one<br>Line two"}]


def test_maybe_send_conflict_alert_uses_dynamic_email_fields(monkeypatch) -> None:
    """Agent decision and draft outputs drive parallel alert delivery."""
    email_calls: list[dict] = []
    sms_calls: list[dict] = []
    push_calls: list[dict] = []

    async def fake_decide_conflict_alert(**_kwargs) -> ConflictAlertDecision:
        return ConflictAlertDecision(send_alert=True)

    async def fake_draft_conflict_alert(**_kwargs) -> ConflictAlertDraft:
        return ConflictAlertDraft(
            subject="Urgent report for DRC Women Peacebuilders",
            issue_summary="Militia violence may be about to break out near City X.",
        )

    async def fake_send_conflict_alert_email(**kwargs) -> None:
        email_calls.append(kwargs)

    async def fake_send_conflict_alert_sms(**kwargs) -> None:
        sms_calls.append(kwargs)

    async def fake_send_conflict_alert_push(**kwargs) -> None:
        push_calls.append(kwargs)

    monkeypatch.setattr(conflict_alerts, "decide_conflict_alert", fake_decide_conflict_alert)
    monkeypatch.setattr(conflict_alerts, "draft_conflict_alert", fake_draft_conflict_alert)
    async def fake_reverse_geocode(**_kwargs) -> str:
        return "Nairobi"

    monkeypatch.setattr(conflict_alerts, "reverse_geocode_short_place_name", fake_reverse_geocode)
    monkeypatch.setattr(conflict_alerts, "send_conflict_alert_email", fake_send_conflict_alert_email)
    monkeypatch.setattr(conflict_alerts, "send_conflict_alert_sms", fake_send_conflict_alert_sms)
    monkeypatch.setattr(conflict_alerts, "send_conflict_alert_push", fake_send_conflict_alert_push)

    sent = asyncio.run(
        maybe_send_conflict_alert(
            async_client=object(),
            chat_model="openai/gpt-4o-mini",
            sendgrid_api_key="test-key",
            sendgrid_from_email="alerts@example.org",
            twilio_account_sid="AC123",
            twilio_auth_token="token",
            twilio_sms_from_number="+19015997398",
            twilio_sms_to_number="+18777804236",
            pushover_user="user-key",
            pushover_token="app-token",
            company_id="company_123",
            company_name="DRC Women Peacebuilders",
            recipient_email="agent-contact@example.org",
            user_message="Militia violence is about to break out near City X.",
            language="English",
            location=(-1.2864, 36.8172),
            google_maps_api_key="maps-key",
        )
    )

    assert sent is True
    assert email_calls[0]["sendgrid_api_key"] == "test-key"
    assert email_calls[0]["sender_email"] == "alerts@example.org"
    assert email_calls[0]["recipient_email"] == "agent-contact@example.org"
    assert email_calls[0]["alert"].subject == "Urgent report for DRC Women Peacebuilders"
    assert "Agent: DRC Women Peacebuilders" in email_calls[0]["alert"].body
    assert "Detected at:" in email_calls[0]["alert"].body
    assert "Location: Nairobi" in email_calls[0]["alert"].body
    assert "City X" in email_calls[0]["alert"].body
    assert sms_calls[0]["twilio_account_sid"] == "AC123"
    assert sms_calls[0]["twilio_auth_token"] == "token"
    assert sms_calls[0]["from_number"] == "+19015997398"
    assert sms_calls[0]["to_number"] == "+18777804236"
    assert sms_calls[0]["alert"].subject == "Urgent report for DRC Women Peacebuilders"
    assert push_calls[0]["pushover_user"] == "user-key"
    assert push_calls[0]["pushover_token"] == "app-token"
    assert push_calls[0]["alert"].subject == "Urgent report for DRC Women Peacebuilders"


def test_maybe_send_conflict_alert_skips_when_decision_agent_says_false(monkeypatch) -> None:
    """The email is not sent when the decision agent says no alert is needed."""
    calls: list[dict] = []

    async def fake_decide_conflict_alert(**_kwargs) -> ConflictAlertDecision:
        return ConflictAlertDecision(send_alert=False)

    async def fake_send_conflict_alert_email(**kwargs) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(conflict_alerts, "decide_conflict_alert", fake_decide_conflict_alert)
    monkeypatch.setattr(conflict_alerts, "send_conflict_alert_email", fake_send_conflict_alert_email)

    sent = asyncio.run(
        maybe_send_conflict_alert(
            async_client=object(),
            chat_model="openai/gpt-4o-mini",
            sendgrid_api_key="test-key",
            sendgrid_from_email="alerts@example.org",
            company_id="company_123",
            company_name="DRC Women Peacebuilders",
            recipient_email="agent-contact@example.org",
            user_message="What does the document say about war recovery programs?",
            language="English",
        )
    )

    assert sent is False
    assert calls == []
