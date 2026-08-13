"""Regression tests for first-party bearer-session configuration and verification."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src.core.auth import UserIdentity, create_session_token, verify_session_token
from src.core.config import (
    DEFAULT_AUTH_SESSION_SECRET,
    MIN_AUTH_SESSION_SECRET_LENGTH,
    Settings,
)


def build_settings(monkeypatch: pytest.MonkeyPatch, **environment: str) -> Settings:
    """Build isolated settings without loading the developer .env file."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///test.db")
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    return Settings(_env_file=None)


def test_production_rejects_the_public_default_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="AUTH_SESSION_SECRET must be explicitly changed"):
        build_settings(
            monkeypatch,
            ENVIRONMENT="production",
            AUTH_SESSION_SECRET=DEFAULT_AUTH_SESSION_SECRET,
        )


def test_production_rejects_a_short_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match=f"at least {MIN_AUTH_SESSION_SECRET_LENGTH} characters"):
        build_settings(
            monkeypatch,
            ENVIRONMENT="production",
            AUTH_SESSION_SECRET="short-session-secret",
        )


def test_production_rejects_the_local_frontend_url(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="FRONTEND_BASE_URL must be set to the public frontend URL"):
        build_settings(
            monkeypatch,
            ENVIRONMENT="production",
            AUTH_SESSION_SECRET="a-secure-rotated-session-secret-with-adequate-length",
            FRONTEND_BASE_URL="http://localhost:3000",
        )


def test_token_signed_with_the_old_default_secret_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    old_secret_settings = build_settings(monkeypatch, AUTH_SESSION_SECRET=DEFAULT_AUTH_SESSION_SECRET)
    forged_token = create_session_token(
        settings=old_secret_settings,
        identity=UserIdentity(user_id="attacker", email="admin@example.com"),
    )
    active_settings = build_settings(
        monkeypatch,
        AUTH_SESSION_SECRET="a-secure-rotated-session-secret-with-adequate-length",
    )

    with pytest.raises(HTTPException) as error:
        verify_session_token(settings=active_settings, token=forged_token)

    assert error.value.status_code == 401
