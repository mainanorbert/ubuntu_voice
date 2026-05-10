"""Tests for cumulative user spend accounting helpers."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.core.database import Base
from src.models import User
from src.services.cost_monitoring import (
    build_usage_charge,
    ensure_user_spend_row,
    list_user_spend_rows,
    merge_usage_charges,
    record_user_spend,
    usage_charge_from_openrouter_usage,
)


def build_session():
    """Create an isolated in-memory database session for spend-tracking tests."""
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_usage_charge_from_openrouter_usage_reads_tokens_and_cost() -> None:
    """Normalize OpenRouter usage objects into the app's internal charge format."""
    usage = SimpleNamespace(
        prompt_tokens=120,
        completion_tokens=30,
        total_tokens=150,
        cost=0.0042,
    )

    charge = usage_charge_from_openrouter_usage(usage)

    assert charge is not None
    assert charge.request_count == 1
    assert charge.prompt_tokens == 120
    assert charge.completion_tokens == 30
    assert charge.total_tokens == 150
    assert charge.cost_usd == Decimal("0.0042")


def test_record_user_spend_accumulates_cost_and_tokens() -> None:
    """Persist multiple usage charges into a single cumulative per-user row."""
    session = build_session()
    session.add(User(id="user_1", email="owner@example.com"))
    session.commit()

    ensure_user_spend_row(session, user_id="user_1", email="owner@example.com")
    record_user_spend(
        session,
        user_id="user_1",
        email="owner@example.com",
        charge=build_usage_charge(
            request_count=2,
            prompt_tokens=100,
            completion_tokens=40,
            total_tokens=140,
            cost_usd=Decimal("0.012300"),
        ),
    )
    record_user_spend(
        session,
        user_id="user_1",
        email="owner@example.com",
        charge=build_usage_charge(
            request_count=1,
            prompt_tokens=25,
            completion_tokens=5,
            total_tokens=30,
            cost_usd=Decimal("0.001500"),
        ),
    )
    session.commit()

    rows = list_user_spend_rows(session)

    assert len(rows) == 1
    row = rows[0]
    assert row.user_id == "user_1"
    assert row.email == "owner@example.com"
    assert row.total_requests == 3
    assert row.total_prompt_tokens == 125
    assert row.total_completion_tokens == 45
    assert row.total_tokens == 170
    assert row.total_cost_usd == Decimal("0.013800")


def test_merge_usage_charges_sums_each_field() -> None:
    """Combine multiple usage charge records into one aggregate summary."""
    merged = merge_usage_charges(
        [
            build_usage_charge(
                request_count=1,
                prompt_tokens=50,
                completion_tokens=10,
                total_tokens=60,
                cost_usd=Decimal("0.002000"),
            ),
            build_usage_charge(
                request_count=3,
                prompt_tokens=90,
                completion_tokens=15,
                total_tokens=105,
                cost_usd=Decimal("0.006500"),
            ),
        ]
    )

    assert merged.request_count == 4
    assert merged.prompt_tokens == 140
    assert merged.completion_tokens == 25
    assert merged.total_tokens == 165
    assert merged.cost_usd == Decimal("0.008500")
