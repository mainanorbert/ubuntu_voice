"""Tests for chat request language and history validation."""

import pytest
from pydantic import ValidationError

from src.api.v1.schemas.agent import AgentChatRequest


def test_agent_chat_request_accepts_supported_languages() -> None:
    """Chat requests accept the supported MVP language set."""
    for language in ["English", "Swahili", "French"]:
        request = AgentChatRequest(company_id="company_1", message="Hello", language=language)
        assert request.language == language


def test_agent_chat_request_defaults_to_english() -> None:
    """Missing language keeps backward-compatible English behavior."""
    request = AgentChatRequest(company_id="company_1", message="Hello")
    assert request.language == "English"
    assert request.history == []


def test_agent_chat_request_rejects_unsupported_language() -> None:
    """Unsupported language names are rejected before prompt construction."""
    with pytest.raises(ValidationError):
        AgentChatRequest(company_id="company_1", message="Hello", language="Arabic")


def test_agent_chat_request_accepts_recent_history() -> None:
    """Chat requests may include bounded recent turns for follow-up retrieval."""
    request = AgentChatRequest(
        company_id="company_1",
        message="Who can I contact there?",
        history=[
            {"role": "user", "content": "Tell me about support in Goma."},
            {"role": "assistant", "content": "The document mentions a Goma support desk."},
        ],
    )

    assert request.history[0].role == "user"
    assert request.history[1].content == "The document mentions a Goma support desk."


def test_agent_chat_request_rejects_too_much_history() -> None:
    """History is capped to keep request context small and privacy-preserving."""
    with pytest.raises(ValidationError):
        AgentChatRequest(
            company_id="company_1",
            message="Continue",
            history=[{"role": "user", "content": f"turn {index}"} for index in range(9)],
        )
