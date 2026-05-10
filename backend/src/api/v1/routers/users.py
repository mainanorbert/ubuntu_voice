"""Routes for syncing authenticated Clerk users into local persistence."""

from typing import Annotated

from clerk_backend_api.security.types import RequestState
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.v1.schemas.ingestion import RegisteredUserResponse
from src.api.v1.schemas.usage import UserSpendResponse
from src.core.clerk_auth import get_authenticated_user_identity, require_clerk_session
from src.core.dependencies import get_db_session
from src.services.cost_monitoring import ensure_user_spend_row, list_user_spend_rows
from src.services.ingestion import upsert_user

router = APIRouter(prefix="/users", tags=["users"])


def build_user_spend_response(row) -> UserSpendResponse:
    """Serialize a cumulative spend ORM row into an API response model."""
    return UserSpendResponse(
        user_id=row.user_id,
        email=row.email,
        total_cost_usd=float(row.total_cost_usd),
        total_requests=row.total_requests,
        total_prompt_tokens=row.total_prompt_tokens,
        total_completion_tokens=row.total_completion_tokens,
        total_tokens=row.total_tokens,
        updated_at=row.updated_at,
    )


@router.post("/register", response_model=RegisteredUserResponse, status_code=status.HTTP_201_CREATED)
async def post_user_register(
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> RegisteredUserResponse:
    """Create the local user row for the signed-in Clerk user if it does not exist yet."""
    identity = get_authenticated_user_identity(session_state)
    user, created = upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    ensure_user_spend_row(db_session, user_id=user.id, email=user.email)
    db_session.commit()
    db_session.refresh(user)
    return RegisteredUserResponse(
        id=user.id,
        email=user.email,
        created=created,
        created_at=user.created_at,
    )


@router.get("/costs", response_model=list[UserSpendResponse])
async def get_user_costs(
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> list[UserSpendResponse]:
    """Return the current cumulative spend totals for all tracked users."""
    identity = get_authenticated_user_identity(session_state)
    user, _created = upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    ensure_user_spend_row(db_session, user_id=user.id, email=user.email)
    db_session.commit()
    rows = list_user_spend_rows(db_session)
    return [build_user_spend_response(row) for row in rows]
