"""Authorization tests for the cumulative usage endpoint."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.v1.routers.users import get_user_costs
from src.core.auth import UserIdentity


def test_usage_endpoint_rejects_a_non_admin_before_reading_usage_details() -> None:
    with pytest.raises(HTTPException) as error:
        asyncio.run(
            get_user_costs(
                session_state=UserIdentity(user_id="user_1", email="member@example.com"),
                settings=SimpleNamespace(admin_emails="admin@example.com"),
                db_session=None,
            )
        )

    assert error.value.status_code == 403
    assert error.value.detail == "Administrator access is required."
