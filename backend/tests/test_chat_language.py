"""Tests for chat language selection and localized fallback responses."""

import pytest
from pydantic import ValidationError

from src.api.v1.schemas.agent import AgentChatRequest
from src.services.rag_agent import build_out_of_scope_reply


def test_agent_chat_request_accepts_supported_languages() -> None:
    """Chat requests accept the supported MVP language set."""
    for language in ["English", "Swahili", "French"]:
        request = AgentChatRequest(company_id="company_1", message="Hello", language=language)
        assert request.language == language


def test_agent_chat_request_defaults_to_english() -> None:
    """Missing language keeps backward-compatible English behavior."""
    request = AgentChatRequest(company_id="company_1", message="Hello")
    assert request.language == "English"


def test_agent_chat_request_rejects_unsupported_language() -> None:
    """Unsupported language names are rejected before prompt construction."""
    with pytest.raises(ValidationError):
        AgentChatRequest(company_id="company_1", message="Hello", language="Arabic")


def test_out_of_scope_reply_is_localized() -> None:
    """No-context fallback replies are fixed strings in the selected language."""
    company_name = "Ubuntu Voice"
    assert build_out_of_scope_reply(company_name=company_name, language="English") == (
        "I don't have enough trusted information in Ubuntu Voice's knowledge base to answer that."
    )
    assert build_out_of_scope_reply(company_name=company_name, language="Swahili") == (
        "Sina taarifa za kutosha zilizoaminika kwenye hifadhidata ya Ubuntu Voice kujibu hilo."
    )
    assert build_out_of_scope_reply(company_name=company_name, language="French") == (
        "Je n'ai pas assez d'informations fiables dans la base de connaissances de Ubuntu Voice pour répondre à cela."
    )
