"""Manual-registration email verification tests."""

import asyncio

import pytest
from fastapi import HTTPException
from sendgrid.helpers.mail import Mail
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.auth import verify_password
from src.core.database import Base
from src.models import PendingEmailVerification, User
from src.services import auth


def test_manual_account_is_created_only_after_email_confirmation() -> None:
    """A pending registration cannot sign in or create a user before its link is used."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        pending, token = auth.start_manual_registration(
            session,
            email=" Person@Example.org ",
            password="SecurePassword1!",
            name="Person Example",
        )
        assert pending.email == "person@example.org"
        assert session.query(User).count() == 0
        assert pending.token_hash != token

        user = auth.confirm_email_verification(session, token=token)
        session.commit()

        assert user.email == "person@example.org"
        assert verify_password("SecurePassword1!", user.password_hash)
        assert session.query(PendingEmailVerification).count() == 0

        with pytest.raises(HTTPException, match="invalid or has expired"):
            auth.confirm_email_verification(session, token=token)


def test_login_with_an_unregistered_email_has_clear_feedback() -> None:
    """Users should be told when the email address has no account."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session, pytest.raises(HTTPException) as error:
        auth.authenticate_manual_user(session, email="missing@example.org", password="SecurePassword1!")

    assert error.value.status_code == 401
    assert error.value.detail == "We couldn't find an account with that email address."


def test_email_verification_uses_configured_sendgrid_sender(monkeypatch) -> None:
    """Confirmation mail is sent through SendGrid using the configured From address."""
    sent_messages: list[Mail] = []

    class FakeResponse:
        status_code = 202

    class FakeSendGridClient:
        def __init__(self, api_key: str) -> None:
            assert api_key == "sendgrid-key"

        def send(self, message: Mail) -> FakeResponse:
            sent_messages.append(message)
            return FakeResponse()

    monkeypatch.setattr(auth, "SendGridAPIClient", FakeSendGridClient)
    asyncio.run(
        auth.send_email_verification_email(
            sendgrid_api_key="sendgrid-key",
            sender_email="verified-sender@example.org",
            recipient_email="person@example.org",
            verification_url="https://app.example.org/confirm-email?token=private-token",
        )
    )

    assert len(sent_messages) == 1
    assert sent_messages[0].from_email.email == "verified-sender@example.org"
    assert sent_messages[0].personalizations[0].tos[0]["email"] == "person@example.org"
