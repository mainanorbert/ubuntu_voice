"""Tests for contextual query preparation before RAG retrieval."""

import asyncio
from types import SimpleNamespace

from src.services.rag_agent import format_chat_history, prepare_retrieval_query


def test_format_chat_history_keeps_recent_valid_turns() -> None:
    """Prompt history is compact and excludes malformed turns."""
    history = [
        {"role": "system", "content": "ignored"},
        {"role": "user", "content": "  Tell me about services in Goma.  "},
        {"role": "assistant", "content": "There is a support desk."},
    ]

    formatted = format_chat_history(history)

    assert "System" not in formatted
    assert "User: Tell me about services in Goma." in formatted
    assert "Assistant: There is a support desk." in formatted


def test_prepare_retrieval_query_can_skip_general_chat() -> None:
    """The initial prompt call can decide that retrieval is unnecessary."""
    calls: list[dict] = []

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"needs_retrieval": false, "query": ""}'))],
                usage=None,
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    needs_retrieval, query, charge = asyncio.run(
        prepare_retrieval_query(
            async_client=fake_client,
            chat_model="test-model",
            company_name="Ubuntu Voice",
            user_message="Hi",
            history=[],
        )
    )

    assert needs_retrieval is False
    assert query == ""
    assert charge is None
    assert calls[0]["model"] == "test-model"


def test_prepare_retrieval_query_rewrites_followup_fact_question() -> None:
    """Fact-seeking follow-ups are rewritten before embedding for retrieval."""
    calls: list[dict] = []

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"needs_retrieval": true, "query": "Goma support desk contact"}'
                        )
                    )
                ],
                usage=None,
            )

    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))

    needs_retrieval, query, charge = asyncio.run(
        prepare_retrieval_query(
            async_client=fake_client,
            chat_model="test-model",
            company_name="Ubuntu Voice",
            user_message="Who can I contact there?",
            history=[{"role": "user", "content": "Tell me about services in Goma."}],
        )
    )

    assert needs_retrieval is True
    assert query == "Goma support desk contact"
    assert charge is None
    assert "Tell me about services in Goma." in calls[0]["messages"][1]["content"]
