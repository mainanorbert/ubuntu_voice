"""Tests for Twilio WhatsApp webhook routing."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.core.database import Base
from src.models import Company, User
from src.services.whatsapp import format_twilio_whatsapp_address, normalize_whatsapp_phone_number


def test_whatsapp_phone_normalization_handles_twilio_addresses() -> None:
    """Twilio WhatsApp addresses normalize to the agent phone format."""
    assert normalize_whatsapp_phone_number("whatsapp:+15551234567") == "+15551234567"
    assert normalize_whatsapp_phone_number("+1 (555) 123-4567") == "+15551234567"
    assert format_twilio_whatsapp_address("+15551234567") == "whatsapp:+15551234567"


def test_twilio_whatsapp_webhook_uses_agent_assigned_to_inbound_number(tmp_path, monkeypatch) -> None:
    """Incoming WhatsApp messages are answered by the company assigned to Twilio's To number."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-clerk-secret")
    monkeypatch.setenv("EIVEN_SERVICE_URL", f"sqlite:///{tmp_path / 'whatsapp.db'}")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "test-account-sid")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-auth-token")
    monkeypatch.setenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+15551234567")

    from src.core.dependencies import clear_database_caches, get_database_engine, get_settings

    clear_database_caches()

    from src.api.v1.routers import webhooks
    from src.main import app

    agent_calls: list[dict] = []
    sent_replies: list[dict] = []

    async def fake_build_whatsapp_agent_reply(**kwargs) -> str:
        agent_calls.append(kwargs)
        return "Congo Agent reply"

    async def fake_send_twilio_whatsapp_reply(**kwargs) -> None:
        sent_replies.append(kwargs)

    monkeypatch.setattr(webhooks, "build_whatsapp_agent_reply", fake_build_whatsapp_agent_reply)
    monkeypatch.setattr(webhooks, "send_twilio_whatsapp_reply", fake_send_twilio_whatsapp_reply)

    try:
        with TestClient(app) as client:
            settings = get_settings()
            engine = get_database_engine(settings.database_url)
            Base.metadata.create_all(bind=engine)
            with Session(engine) as session:
                session.add(User(id="owner_1", email="owner@example.org"))
                session.add(
                    Company(
                        id="company_1",
                        name="Congo Agent",
                        email="agent@example.org",
                        phone="+15551234567",
                        owner_id="owner_1",
                    )
                )
                session.commit()

            response = client.post(
                "/api/v1/webhooks/whatsapp/twilio",
                data={
                    "Body": "hi, how are you",
                    "From": "whatsapp:+254711222333",
                    "To": "whatsapp:+15551234567",
                    "MessageSid": "SM_test",
                },
            )

        assert response.status_code == 200
        assert response.text == "OK"
        assert agent_calls[0]["company"].name == "Congo Agent"
        assert agent_calls[0]["user_message"] == "hi, how are you"
        assert sent_replies[0]["from_number"] == "whatsapp:+15551234567"
        assert sent_replies[0]["to_number"] == "whatsapp:+254711222333"
        assert sent_replies[0]["body"] == "Congo Agent reply"
    finally:
        clear_database_caches()


def test_twilio_whatsapp_webhook_ignores_unknown_inbound_number(tmp_path, monkeypatch) -> None:
    """Unknown Twilio recipient numbers do not fall back to the wrong agent."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-clerk-secret")
    monkeypatch.setenv("EIVEN_SERVICE_URL", f"sqlite:///{tmp_path / 'whatsapp_unknown.db'}")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "test-account-sid")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-auth-token")
    monkeypatch.setenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+15551234567")

    from src.core.dependencies import clear_database_caches

    clear_database_caches()

    from src.api.v1.routers import webhooks
    from src.main import app

    sent_replies: list[dict] = []

    async def fake_send_twilio_whatsapp_reply(**kwargs) -> None:
        sent_replies.append(kwargs)

    monkeypatch.setattr(webhooks, "send_twilio_whatsapp_reply", fake_send_twilio_whatsapp_reply)

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/webhooks/whatsapp/twilio",
                data={
                    "Body": "hello",
                    "From": "whatsapp:+254711222333",
                    "To": "whatsapp:+15550000000",
                    "MessageSid": "SM_unknown",
                },
            )

        assert response.status_code == 200
        assert response.text == "OK"
        assert sent_replies == []
    finally:
        clear_database_caches()
