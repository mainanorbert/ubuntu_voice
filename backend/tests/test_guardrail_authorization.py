"""Authorization tests for guardrail audit-event monitoring."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.v1.routers.monitoring import list_guardrail_events
from src.core.auth import UserIdentity


def test_guardrail_events_reject_a_non_admin_before_reading_audit_data() -> None:
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            list_guardrail_events(
                session_state=UserIdentity(user_id="user_1", email="member@example.com"),
                settings=SimpleNamespace(admin_emails="admin@example.com"),
                db_session=None,
            )
        )

    assert error.value.status_code == 403
    assert error.value.detail == "Administrator access is required."
