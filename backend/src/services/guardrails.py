"""Safety guardrails for the RAG chat endpoint.

This module owns two responsibilities:

1. Pre-input checks – count tokens in the user prompt with ``tiktoken`` and
   reject oversized requests *before* any embedding or LLM call so cost stays
   predictable and answers stay focused.
2. Post-output checks – scan the assistant reply for personal information
   (emails, phone numbers in the configured country code) so flagged
   exchanges can be persisted to ``guardrail_events`` for later review.

All persistence helpers commit their own transaction so a logging failure
never silently corrupts the caller's main session.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache

import tiktoken
from sqlalchemy.orm import Session

from src.models import GuardrailEvent

logger = logging.getLogger(__name__)


# ── Detection patterns ────────────────────────────────────────────────────────

EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=8)
def _phone_pattern_for_country(country_code: str) -> re.Pattern[str]:
    """Build (and cache) a phone-number regex for a given dialing code.

    Recognises three common shapes for a country (defaulting to Kenyan +254
    layouts):

    - international with plus, e.g. ``+254712345678``
    - international without plus, e.g. ``254712345678``
    - local trunk-zero form, e.g. ``0712345678``

    The trunk-zero form is included only when the country code is ``254``,
    which matches the documented use-case of monitoring Kenyan numbers.
    """
    cc = re.escape(country_code.strip().lstrip("+"))
    if cc == "254":
        pattern = rf"(?:\+?{cc}|0)7\d{{8}}\b"
    else:
        pattern = rf"\+?{cc}\d{{6,12}}\b"
    return re.compile(pattern)


# ── Token counting ────────────────────────────────────────────────────────────

@lru_cache(maxsize=8)
def _get_encoding(encoding_name: str) -> tiktoken.Encoding:
    """Return a cached tiktoken encoding, falling back to ``cl100k_base``."""
    try:
        return tiktoken.get_encoding(encoding_name)
    except (KeyError, ValueError):
        logger.warning(
            "Unknown tiktoken encoding %r; falling back to cl100k_base.",
            encoding_name,
        )
        return tiktoken.get_encoding("cl100k_base")


def count_input_tokens(text: str, *, encoding_name: str) -> int:
    """Return the token count for ``text`` using the configured encoding."""
    encoding = _get_encoding(encoding_name)
    return len(encoding.encode(text or ""))


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class InputCheckResult:
    """Outcome of pre-input guardrail evaluation."""

    allowed: bool
    token_count: int
    limit: int
    reason: str | None = None


@dataclass(frozen=True)
class OutputCheckResult:
    """Outcome of post-output guardrail evaluation."""

    triggered: bool
    matched_rules: list[str] = field(default_factory=list)


# ── Public API: input ─────────────────────────────────────────────────────────

def evaluate_input(
    *,
    message: str,
    max_tokens: int,
    encoding_name: str,
) -> InputCheckResult:
    """Decide whether a user prompt is allowed through to the model.

    Currently enforces a single rule: token count must not exceed
    ``max_tokens``. Designed so additional rules (banned topics, PII in the
    prompt, etc.) can be layered in later without changing the call site.
    """
    token_count = count_input_tokens(message, encoding_name=encoding_name)
    if token_count > max_tokens:
        reason = (
            f"Your message is too long ({token_count} tokens). "
            f"Please keep requests under {max_tokens} tokens and ask one "
            "focused question at a time."
        )
        return InputCheckResult(
            allowed=False,
            token_count=token_count,
            limit=max_tokens,
            reason=reason,
        )
    return InputCheckResult(allowed=True, token_count=token_count, limit=max_tokens)


# ── Public API: output ────────────────────────────────────────────────────────

def evaluate_output(*, reply: str, phone_country_code: str) -> OutputCheckResult:
    """Detect monitored personal information in an assistant reply."""
    matched: list[str] = []

    if EMAIL_PATTERN.search(reply or ""):
        matched.append("email")

    phone_pattern = _phone_pattern_for_country(phone_country_code)
    if phone_pattern.search(reply or ""):
        matched.append("phone")

    return OutputCheckResult(triggered=bool(matched), matched_rules=matched)


# ── Persistence ───────────────────────────────────────────────────────────────

def record_guardrail_event(
    db_session: Session,
    *,
    user_id: str | None,
    company_id: str | None,
    event_type: str,
    action: str,
    matched_rules: list[str] | None,
    prompt_text: str | None,
    response_text: str | None,
    input_token_count: int | None,
) -> None:
    """Persist a guardrail trigger to ``guardrail_events``.

    Uses an isolated transaction so an audit-write failure (e.g. transient DB
    error) never breaks the user's chat request. Errors are logged but
    swallowed because monitoring must not be a hard dependency of the reply
    path.
    """
    try:
        event = GuardrailEvent(
            user_id=user_id,
            company_id=company_id,
            event_type=event_type,
            action=action,
            matched_rules={"rules": matched_rules} if matched_rules else None,
            prompt_text=prompt_text,
            response_text=response_text,
            input_token_count=input_token_count,
        )
        db_session.add(event)
        db_session.commit()
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to record guardrail event (type=%s, action=%s)",
            event_type,
            action,
        )
        db_session.rollback()
