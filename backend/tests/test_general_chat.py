"""Tests for non-RAG conversational chat behavior."""

from src.services.rag_agent import (
    build_conflict_report_reply,
    build_general_conversation_reply,
    is_general_conversation,
    is_simple_conflict_report,
)


def test_general_conversation_detection_handles_greetings() -> None:
    """Short greetings and simple help prompts bypass document retrieval."""
    assert is_general_conversation("hi")
    assert is_general_conversation("How are you?")
    assert is_general_conversation("what can you help with?")
    assert not is_general_conversation("What does the document say about reporting contacts in Goma?")


def test_general_conversation_reply_mentions_agent_documents() -> None:
    """General replies remain helpful while pointing users back to trusted sources."""
    reply = build_general_conversation_reply(company_name="Sahel Peace Mediator", language="English")
    assert "ready to help" in reply
    assert "Sahel Peace Mediator's trusted documents" in reply
    assert "reporting contacts" in reply


def test_simple_conflict_report_bypasses_rag_fallback() -> None:
    """Declarative emerging-conflict reports get a courteous support response."""
    assert is_simple_conflict_report("There is a war about to break in Kinshasa due to armed men in the city")
    assert not is_simple_conflict_report("There is a war about to break in Kinshasa. Who can I contact?")


def test_conflict_report_reply_offers_support_options() -> None:
    """Conflict-report replies ask how to help without inventing local contacts."""
    reply = build_conflict_report_reply(company_name="DRC Women Peacebuilders", language="English")
    assert "short report" in reply
    assert "trusted documents" in reply
    assert "reporting contacts" in reply
