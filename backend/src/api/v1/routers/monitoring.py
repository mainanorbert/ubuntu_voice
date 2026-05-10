"""Read-only endpoints that surface guardrail audit data to the dashboard."""

from typing import Annotated

from clerk_backend_api.security.types import RequestState
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.api.v1.schemas.monitoring import GuardrailEventResponse
from src.core.clerk_auth import get_authenticated_user_identity, require_clerk_session
from src.core.dependencies import get_db_session
from src.models import GuardrailEvent
from src.services.ingestion import upsert_user

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def build_guardrail_event_response(event: GuardrailEvent) -> GuardrailEventResponse:
    """Serialize a ``GuardrailEvent`` row into the API response model."""
    rules: list[str] = []
    if isinstance(event.matched_rules, dict):
        raw_rules = event.matched_rules.get("rules")
        if isinstance(raw_rules, list):
            rules = [str(rule) for rule in raw_rules]
    return GuardrailEventResponse(
        id=event.id,
        user_id=event.user_id,
        company_id=event.company_id,
        event_type=event.event_type,
        action=event.action,
        matched_rules=rules,
        prompt_text=event.prompt_text,
        response_text=event.response_text,
        input_token_count=event.input_token_count,
        created_at=event.created_at,
    )


@router.get("/guardrail-events", response_model=list[GuardrailEventResponse])
async def list_guardrail_events(
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[GuardrailEventResponse]:
    """Return the most recent guardrail audit rows in reverse chronological order.

    The signed-in user is upserted into the local users table (mirroring the
    other routes) so dashboard access works for newly authenticated operators.
    Rows are returned newest-first; ``limit`` caps the page size to keep the
    payload small for the dashboard.
    """
    identity = get_authenticated_user_identity(session_state)
    upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    db_session.commit()

    events = (
        db_session.query(GuardrailEvent)
        .order_by(GuardrailEvent.created_at.desc())
        .limit(limit)
        .all()
    )
    return [build_guardrail_event_response(event) for event in events]
