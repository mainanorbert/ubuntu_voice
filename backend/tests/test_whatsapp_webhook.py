"""Tests for Twilio WhatsApp agent selection and session routing."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.core.database import Base
from src.models import Company, User, WhatsAppAgentSession
from src.services.whatsapp import (
    build_whatsapp_participant_hash,
    format_twilio_whatsapp_address,
    normalize_whatsapp_phone_number,
)

TWILIO_NUMBER = "whatsapp:+15551234567"
PARTICIPANT_NUMBER = "whatsapp:+254711222333"


def configure_whatsapp_test_app(tmp_path, monkeypatch, database_name: str):
    """Configure the application with an isolated WhatsApp test database."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-clerk-secret")
    monkeypatch.setenv("EIVEN_SERVICE_URL", f"sqlite:///{tmp_path / database_name}")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "test-account-sid")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test-auth-token")
    monkeypatch.setenv("TWILIO_WHATSAPP_NUMBER", TWILIO_NUMBER)
    monkeypatch.setenv("WHATSAPP_SESSION_TIMEOUT_MINUTES", "60")

    from src.core.dependencies import clear_database_caches, get_database_engine, get_settings

    clear_database_caches()

    from src.api.v1.routers import webhooks
    from src.main import app

    settings = get_settings()
    engine = get_database_engine(settings.database_url)
    Base.metadata.create_all(bind=engine)
    return app, webhooks, engine, clear_database_caches


def seed_agents(engine) -> None:
    """Create two agents whose stable ordering is used by the WhatsApp menu."""
    with Session(engine) as session:
        session.add(User(id="owner_1", email="owner@example.org"))
        session.add_all(
            [
                Company(
                    id="company_1",
                    name="Congo Agent",
                    email="congo@example.org",
                    owner_id="owner_1",
                ),
                Company(
                    id="company_2",
                    name="Sahel Agent",
                    email="sahel@example.org",
                    owner_id="owner_1",
                ),
            ]
        )
        session.commit()


def test_whatsapp_phone_normalization_and_participant_hashing() -> None:
    """WhatsApp addresses normalize while participant identifiers remain opaque."""
    assert normalize_whatsapp_phone_number("whatsapp:+15551234567") == "+15551234567"
    assert normalize_whatsapp_phone_number("+1 (555) 123-4567") == "+15551234567"
    assert format_twilio_whatsapp_address("+15551234567") == "whatsapp:+15551234567"

    participant_hash = build_whatsapp_participant_hash(
        phone_number=PARTICIPANT_NUMBER,
        secret="test-secret",
    )
    assert len(participant_hash) == 64
    assert "254711222333" not in participant_hash


def test_whatsapp_first_contact_selects_agent_and_routes_session(tmp_path, monkeypatch) -> None:
    """A first contact receives the DB menu, selects an agent, then reaches that agent."""
    app, webhooks, engine, clear_database_caches = configure_whatsapp_test_app(
        tmp_path,
        monkeypatch,
        "whatsapp_session.db",
    )
    seed_agents(engine)
    agent_calls: list[dict] = []
    sent_replies: list[dict] = []

    async def fake_build_whatsapp_agent_reply(**kwargs) -> str:
        agent_calls.append(kwargs)
        return "Sahel response"

    async def fake_send_twilio_whatsapp_reply(**kwargs) -> None:
        sent_replies.append(kwargs)

    monkeypatch.setattr(webhooks, "build_whatsapp_agent_reply", fake_build_whatsapp_agent_reply)
    monkeypatch.setattr(webhooks, "send_twilio_whatsapp_reply", fake_send_twilio_whatsapp_reply)

    try:
        with TestClient(app) as client:
            first_response = client.post(
                "/api/v1/webhooks/whatsapp/twilio",
                data={"Body": "2", "From": PARTICIPANT_NUMBER, "To": TWILIO_NUMBER, "MessageSid": "SM_first"},
            )
            invalid_response = client.post(
                "/api/v1/webhooks/whatsapp/twilio",
                data={"Body": "99", "From": PARTICIPANT_NUMBER, "To": TWILIO_NUMBER, "MessageSid": "SM_invalid"},
            )
            selection_response = client.post(
                "/api/v1/webhooks/whatsapp/twilio",
                data={"Body": "2", "From": PARTICIPANT_NUMBER, "To": TWILIO_NUMBER, "MessageSid": "SM_select"},
            )
            with Session(engine) as session:
                selected_at = session.query(WhatsAppAgentSession).one().last_activity_at
            chat_response = client.post(
                "/api/v1/webhooks/whatsapp/twilio",
                data={
                    "Body": "Where can I find mediation support?",
                    "From": PARTICIPANT_NUMBER,
                    "To": TWILIO_NUMBER,
                    "MessageSid": "SM_chat",
                },
            )

        assert first_response.status_code == 200
        assert invalid_response.status_code == 200
        assert selection_response.status_code == 200
        assert chat_response.status_code == 200
        assert "1. Congo Agent" in sent_replies[0]["body"]
        assert "2. Sahel Agent" in sent_replies[0]["body"]
        assert "That selection is not available." in sent_replies[1]["body"]
        assert "now chatting with Sahel Agent" in sent_replies[2]["body"]
        assert sent_replies[3]["body"] == "Sahel response"
        assert agent_calls[0]["company"].id == "company_2"
        assert agent_calls[0]["user_message"] == "Where can I find mediation support?"

        with Session(engine) as session:
            stored_session = session.query(WhatsAppAgentSession).one()
            assert stored_session.company_id == "company_2"
            assert stored_session.recipient_number == "+15551234567"
            assert stored_session.participant_hash != normalize_whatsapp_phone_number(PARTICIPANT_NUMBER)
            assert stored_session.last_activity_at > selected_at
    finally:
        clear_database_caches()


def test_whatsapp_expired_session_returns_current_agent_menu(tmp_path, monkeypatch) -> None:
    """An inactive selection expires after one hour and does not invoke its previous agent."""
    app, webhooks, engine, clear_database_caches = configure_whatsapp_test_app(
        tmp_path,
        monkeypatch,
        "whatsapp_expired.db",
    )
    seed_agents(engine)
    sent_replies: list[dict] = []
    agent_calls: list[dict] = []

    async def fake_build_whatsapp_agent_reply(**kwargs) -> str:
        agent_calls.append(kwargs)
        return "Unexpected response"

    async def fake_send_twilio_whatsapp_reply(**kwargs) -> None:
        sent_replies.append(kwargs)

    monkeypatch.setattr(webhooks, "build_whatsapp_agent_reply", fake_build_whatsapp_agent_reply)
    monkeypatch.setattr(webhooks, "send_twilio_whatsapp_reply", fake_send_twilio_whatsapp_reply)

    participant_hash = build_whatsapp_participant_hash(
        phone_number=PARTICIPANT_NUMBER,
        secret="test-auth-token",
    )
    with Session(engine) as session:
        session.add(
            WhatsAppAgentSession(
                recipient_number="+15551234567",
                participant_hash=participant_hash,
                company_id="company_1",
                last_activity_at=datetime.now(timezone.utc) - timedelta(minutes=61),
            )
        )
        session.commit()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/webhooks/whatsapp/twilio",
                data={
                    "Body": "Is anyone there?",
                    "From": PARTICIPANT_NUMBER,
                    "To": TWILIO_NUMBER,
                    "MessageSid": "SM_expired",
                },
            )

        assert response.status_code == 200
        assert "Choose an agent" in sent_replies[0]["body"]
        assert agent_calls == []
        with Session(engine) as session:
            stored_session = session.query(WhatsAppAgentSession).one()
            assert stored_session.company_id is None
    finally:
        clear_database_caches()


def test_whatsapp_menu_command_clears_active_selection(tmp_path, monkeypatch) -> None:
    """An active participant can explicitly return to the agent menu."""
    app, webhooks, engine, clear_database_caches = configure_whatsapp_test_app(
        tmp_path,
        monkeypatch,
        "whatsapp_switch.db",
    )
    seed_agents(engine)
    sent_replies: list[dict] = []

    async def fake_send_twilio_whatsapp_reply(**kwargs) -> None:
        sent_replies.append(kwargs)

    monkeypatch.setattr(webhooks, "send_twilio_whatsapp_reply", fake_send_twilio_whatsapp_reply)
    participant_hash = build_whatsapp_participant_hash(
        phone_number=PARTICIPANT_NUMBER,
        secret="test-auth-token",
    )
    with Session(engine) as session:
        session.add(
            WhatsAppAgentSession(
                recipient_number="+15551234567",
                participant_hash=participant_hash,
                company_id="company_1",
            )
        )
        session.commit()

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/webhooks/whatsapp/twilio",
                data={"Body": "MENU", "From": PARTICIPANT_NUMBER, "To": TWILIO_NUMBER, "MessageSid": "SM_menu"},
            )

        assert response.status_code == 200
        assert "Choose an agent" in sent_replies[0]["body"]
        with Session(engine) as session:
            stored_session = session.query(WhatsAppAgentSession).one()
            assert stored_session.company_id is None
    finally:
        clear_database_caches()


def test_whatsapp_webhook_ignores_unknown_inbound_number(tmp_path, monkeypatch) -> None:
    """Only the configured registered WhatsApp number can start a routing session."""
    app, webhooks, _engine, clear_database_caches = configure_whatsapp_test_app(
        tmp_path,
        monkeypatch,
        "whatsapp_unknown.db",
    )
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
                    "From": PARTICIPANT_NUMBER,
                    "To": "whatsapp:+15550000000",
                    "MessageSid": "SM_unknown",
                },
            )

        assert response.status_code == 200
        assert sent_replies == []
    finally:
        clear_database_caches()
