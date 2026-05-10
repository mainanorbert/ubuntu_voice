"""Helpers for tracking OpenRouter usage and cumulative user spend."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
from sqlalchemy.orm import Session

from src.models import UserSpend


@dataclass(frozen=True)
class UsageCharge:
    """Normalized cost and token accounting for one or more model requests."""

    request_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: Decimal


def decimal_from_value(value: Any) -> Decimal:
    """Convert a provider numeric value into a Decimal without float drift."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def build_usage_charge(
    *,
    request_count: int,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: Decimal,
) -> UsageCharge:
    """Build a normalized usage charge object."""
    return UsageCharge(
        request_count=max(request_count, 0),
        prompt_tokens=max(prompt_tokens, 0),
        completion_tokens=max(completion_tokens, 0),
        total_tokens=max(total_tokens, 0),
        cost_usd=max(cost_usd, Decimal("0")),
    )


def usage_charge_from_openrouter_usage(usage: Any, *, request_count: int = 1) -> UsageCharge | None:
    """Convert an OpenRouter usage object into a normalized charge record."""
    if usage is None:
        return None

    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
    cost_usd = decimal_from_value(getattr(usage, "cost", None))

    if prompt_tokens == 0 and completion_tokens == 0 and total_tokens == 0 and cost_usd == 0:
        return None

    return build_usage_charge(
        request_count=request_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
    )


def merge_usage_charges(charges: list[UsageCharge]) -> UsageCharge:
    """Combine multiple usage charges into a single cumulative total."""
    total_cost_usd = Decimal("0")
    total_requests = 0
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0

    for charge in charges:
        total_cost_usd += charge.cost_usd
        total_requests += charge.request_count
        total_prompt_tokens += charge.prompt_tokens
        total_completion_tokens += charge.completion_tokens
        total_tokens += charge.total_tokens

    return build_usage_charge(
        request_count=total_requests,
        prompt_tokens=total_prompt_tokens,
        completion_tokens=total_completion_tokens,
        total_tokens=total_tokens,
        cost_usd=total_cost_usd,
    )


def ensure_user_spend_row(session: Session, *, user_id: str, email: str | None) -> UserSpend:
    """Return the persistent spend row for a user, creating it if necessary."""
    row = session.get(UserSpend, user_id)
    if row is None:
        row = UserSpend(user_id=user_id, email=email)
        session.add(row)
        session.flush()
        return row

    if email and row.email != email:
        row.email = email
        session.flush()
    return row


def record_user_spend(session: Session, *, user_id: str, email: str | None, charge: UsageCharge) -> UserSpend:
    """Accumulate a usage charge into the user's spend totals."""
    row = ensure_user_spend_row(session, user_id=user_id, email=email)
    row.total_cost_usd += charge.cost_usd
    row.total_requests += charge.request_count
    row.total_prompt_tokens += charge.prompt_tokens
    row.total_completion_tokens += charge.completion_tokens
    row.total_tokens += charge.total_tokens
    session.flush()
    return row


def list_user_spend_rows(session: Session) -> list[UserSpend]:
    """Return all tracked user spend rows sorted by highest total cost."""
    return (
        session.query(UserSpend)
        .order_by(UserSpend.total_cost_usd.desc(), UserSpend.updated_at.desc(), UserSpend.user_id.asc())
        .all()
    )


async def fetch_openrouter_generation_charge(
    *,
    api_key: str,
    base_url: str,
    generation_id: str,
) -> UsageCharge | None:
    """Fetch actual billed usage for one OpenRouter generation."""
    if not generation_id:
        return None

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"{base_url.rstrip('/')}/generation",
            params={"id": generation_id},
            headers={"Authorization": f"Bearer {api_key}"},
        )

    if response.status_code != 200:
        return None

    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return None

    prompt_tokens = int(data.get("tokens_prompt") or 0)
    completion_tokens = int(data.get("tokens_completion") or 0)
    total_tokens = prompt_tokens + completion_tokens
    cost_usd = decimal_from_value(data.get("total_cost"))

    if prompt_tokens == 0 and completion_tokens == 0 and cost_usd == 0:
        return None

    return build_usage_charge(
        request_count=1,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
    )


async def fetch_openrouter_generation_charges(
    *,
    api_key: str,
    base_url: str,
    generation_ids: list[str],
) -> list[UsageCharge]:
    """Fetch billed usage for a list of OpenRouter generation ids."""
    unique_ids: list[str] = []
    seen_ids: set[str] = set()
    for generation_id in generation_ids:
        if generation_id and generation_id not in seen_ids:
            unique_ids.append(generation_id)
            seen_ids.add(generation_id)

    charges: list[UsageCharge] = []
    for generation_id in unique_ids:
        charge = await fetch_openrouter_generation_charge(
            api_key=api_key,
            base_url=base_url,
            generation_id=generation_id,
        )
        if charge is not None:
            charges.append(charge)
    return charges
