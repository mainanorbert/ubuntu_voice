"""Tests for prompt-based query preparation decisions."""

from src.services.rag_agent import parse_query_preparation


def test_parse_query_preparation_skips_retrieval_for_general_chat() -> None:
    """Prompt decisions can skip retrieval for general conversation."""
    needs_retrieval, query = parse_query_preparation(
        '{"needs_retrieval": false, "query": ""}',
        fallback_query="hi",
    )

    assert needs_retrieval is False
    assert query == ""


def test_parse_query_preparation_uses_rewritten_fact_query() -> None:
    """Prompt decisions can provide a focused query for factual retrieval."""
    needs_retrieval, query = parse_query_preparation(
        '{"needs_retrieval": true, "query": "Goma reporting contacts for displaced women"}',
        fallback_query="Who can I contact there?",
    )

    assert needs_retrieval is True
    assert query == "Goma reporting contacts for displaced women"


def test_parse_query_preparation_falls_back_to_retrieval_on_bad_json() -> None:
    """Malformed model output falls back to retrieval instead of skipping facts."""
    needs_retrieval, query = parse_query_preparation("not json", fallback_query="Where is the office?")

    assert needs_retrieval is True
    assert query == "Where is the office?"
