"""Tests for chat safety guardrails."""

from src.services.guardrails import evaluate_input


def test_oversized_input_has_a_clear_user_facing_message() -> None:
    """Length-limit feedback must not expose token-count implementation details."""
    result = evaluate_input(
        message="hello " * 100,
        max_tokens=1,
        encoding_name="cl100k_base",
    )

    assert result.allowed is False
    assert result.reason == "Your message is too long. Please shorten it and try again."
