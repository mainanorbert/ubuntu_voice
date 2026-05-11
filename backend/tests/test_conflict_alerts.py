"""Tests for emerging-conflict email alert detection and redaction."""

import asyncio

from src.services import conflict_alerts
from src.services.conflict_alerts import (
    ConflictAlertDecision,
    ConflictAlertDraft,
    build_conflict_alert_from_draft,
    maybe_send_conflict_alert,
    redact_personal_contact_details,
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


def test_maybe_send_conflict_alert_uses_dynamic_email_fields(monkeypatch) -> None:
    """Agent decision and draft outputs drive the sent alert email."""
    calls: list[dict] = []

    async def fake_decide_conflict_alert(**_kwargs) -> ConflictAlertDecision:
        return ConflictAlertDecision(send_alert=True)

    async def fake_draft_conflict_alert(**_kwargs) -> ConflictAlertDraft:
        return ConflictAlertDraft(
            subject="Urgent report for DRC Women Peacebuilders",
            issue_summary="Militia violence may be about to break out near City X.",
        )

    async def fake_send_conflict_alert_email(**kwargs) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(conflict_alerts, "decide_conflict_alert", fake_decide_conflict_alert)
    monkeypatch.setattr(conflict_alerts, "draft_conflict_alert", fake_draft_conflict_alert)
    monkeypatch.setattr(conflict_alerts, "send_conflict_alert_email", fake_send_conflict_alert_email)

    sent = asyncio.run(
        maybe_send_conflict_alert(
            async_client=object(),
            chat_model="openai/gpt-4o-mini",
            sendgrid_api_key="test-key",
            company_id="company_123",
            company_name="DRC Women Peacebuilders",
            recipient_email="agent-contact@example.org",
            user_message="Militia violence is about to break out near City X.",
            language="English",
        )
    )

    assert sent is True
    assert calls[0]["sendgrid_api_key"] == "test-key"
    assert calls[0]["sender_email"] == "osiemomaina85@gmail.com"
    assert calls[0]["recipient_email"] == "agent-contact@example.org"
    assert calls[0]["alert"].subject == "Urgent report for DRC Women Peacebuilders"
    assert "Agent: DRC Women Peacebuilders" in calls[0]["alert"].body
    assert "Detected at:" in calls[0]["alert"].body
    assert "City X" in calls[0]["alert"].body


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
            company_id="company_123",
            company_name="DRC Women Peacebuilders",
            recipient_email="agent-contact@example.org",
            user_message="What does the document say about war recovery programs?",
            language="English",
        )
    )

    assert sent is False
    assert calls == []
