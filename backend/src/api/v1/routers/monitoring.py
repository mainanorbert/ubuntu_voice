"""Read-only endpoints that surface guardrail audit data to the dashboard."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.v1.schemas.monitoring import GuardrailEventResponse, IncidentStatisticResponse, IncidentStatisticUpdate, IncidentStatisticsAgent, IncidentStatisticsPageResponse, IncidentStatisticsSummary, KnownPlaceInput, KnownPlaceResponse
from src.core.auth import UserIdentity, get_authenticated_user_identity, require_admin, require_auth_session
from src.core.config import Settings
from src.core.dependencies import get_db_session, get_settings
from src.models import Company, GuardrailEvent, IncidentStatistic, KnownPlace
from src.services.incident_statistics import normalize_incident_place, sanitize_incident_description
from src.services.ingestion import upsert_user

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


def place_response(place: KnownPlace) -> KnownPlaceResponse:
    return KnownPlaceResponse.model_validate(place, from_attributes=True)


@router.get("/known-places", response_model=list[KnownPlaceResponse])
async def list_known_places(
    _session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
    include_inactive: bool = False,
) -> list[KnownPlaceResponse]:
    query = db_session.query(KnownPlace)
    if not include_inactive:
        query = query.filter(KnownPlace.is_active.is_(True))
    return [place_response(place) for place in query.order_by(KnownPlace.name).all()]


@router.post("/known-places", response_model=KnownPlaceResponse, status_code=201)
async def create_known_place(
    payload: KnownPlaceInput,
    _session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> KnownPlaceResponse:
    """Create a known place for any signed-in user."""
    place = KnownPlace(
        name=payload.name.strip(),
        country=payload.country.strip() if payload.country and payload.country.strip() else None,
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    if not place.name:
        raise HTTPException(status_code=422, detail="Place name is required.")
    if db_session.query(KnownPlace).filter(KnownPlace.name == place.name).first():
        raise HTTPException(status_code=409, detail="A place with this name already exists.")
    db_session.add(place)
    db_session.commit()
    db_session.refresh(place)
    return place_response(place)


@router.put("/known-places/{place_id}", response_model=KnownPlaceResponse)
async def update_known_place(
    place_id: int,
    payload: KnownPlaceInput,
    _session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> KnownPlaceResponse:
    """Update a known place for any signed-in user."""
    place = db_session.get(KnownPlace, place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found.")
    name = payload.name.strip()
    duplicate = db_session.query(KnownPlace).filter(KnownPlace.name == name, KnownPlace.id != place_id).first()
    if not name:
        raise HTTPException(status_code=422, detail="Place name is required.")
    if duplicate:
        raise HTTPException(status_code=409, detail="A place with this name already exists.")
    place.name = name
    place.country = payload.country.strip() if payload.country and payload.country.strip() else None
    place.latitude, place.longitude = payload.latitude, payload.longitude
    db_session.commit()
    db_session.refresh(place)
    return place_response(place)


@router.delete("/known-places/{place_id}", status_code=204)
async def delete_known_place(
    place_id: int,
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> None:
    """Deactivate a known place for configured administrators only."""
    require_admin(get_authenticated_user_identity(session_state), settings)
    place = db_session.get(KnownPlace, place_id)
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found.")
    place.is_active = False
    db_session.commit()


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


def build_incident_statistic_response(row: IncidentStatistic, company_name: str) -> IncidentStatisticResponse:
    """Serialize an incident-statistics ORM row into the API response model."""
    return IncidentStatisticResponse(
        id=row.id,
        company_id=row.company_id,
        company_name=company_name,
        place=row.place,
        description=row.description,
        type=row.type,
        total_count=row.total_count,
        updated_at=row.updated_at,
    )


@router.put("/incident-statistics/{statistic_id}", response_model=IncidentStatisticResponse)
async def update_incident_statistic(
    statistic_id: str,
    payload: IncidentStatisticUpdate,
    _session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> IncidentStatisticResponse:
    """Allow any signed-in user to correct an aggregated incident row."""
    row = db_session.get(IncidentStatistic, statistic_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Statistic not found.")

    place = payload.place.strip()
    description = sanitize_incident_description(payload.description)
    normalized_place = normalize_incident_place(place)
    if not normalized_place:
        raise HTTPException(status_code=422, detail="Place is required.")
    if not description:
        raise HTTPException(status_code=422, detail="Description is required.")

    duplicate = (
        db_session.query(IncidentStatistic)
        .filter(
            IncidentStatistic.company_id == row.company_id,
            IncidentStatistic.normalized_place == normalized_place,
            IncidentStatistic.type == payload.type,
            IncidentStatistic.id != row.id,
        )
        .first()
    )
    if duplicate is not None:
        raise HTTPException(
            status_code=409,
            detail="A statistic for this agent, place, and category already exists. Edit that row instead.",
        )

    row.place = place
    row.normalized_place = normalized_place
    row.description = description
    row.type = payload.type
    row.total_count = payload.total_count
    db_session.commit()
    db_session.refresh(row)
    company_name = db_session.query(Company.name).filter(Company.id == row.company_id).scalar()
    return build_incident_statistic_response(row, company_name)


@router.delete("/incident-statistics/{statistic_id}", status_code=204)
async def delete_incident_statistic(
    statistic_id: str,
    _session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> None:
    """Allow configured administrators to remove an incorrect incident statistic."""
    require_admin(get_authenticated_user_identity(_session_state), settings)
    row = db_session.get(IncidentStatistic, statistic_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Statistic not found.")
    db_session.delete(row)
    db_session.commit()


@router.get("/guardrail-events", response_model=list[GuardrailEventResponse])
async def list_guardrail_events(
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[GuardrailEventResponse]:
    """Return the most recent guardrail audit rows in reverse chronological order.

    The signed-in user is upserted into the local users table (matching the
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


@router.get("/incident-statistics", response_model=IncidentStatisticsPageResponse)
async def list_incident_statistics(
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
    agent_id: Annotated[str | None, Query(min_length=1, max_length=36)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> IncidentStatisticsPageResponse:
    """Return paginated incident statistics from every agent to signed-in users."""
    identity = get_authenticated_user_identity(session_state)
    upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    db_session.commit()

    base_query = db_session.query(IncidentStatistic).join(Company, Company.id == IncidentStatistic.company_id)
    if agent_id is not None:
        base_query = base_query.filter(IncidentStatistic.company_id == agent_id)

    total = base_query.count()
    total_reports, places, categories = base_query.with_entities(
        func.coalesce(func.sum(IncidentStatistic.total_count), 0),
        func.count(func.distinct(IncidentStatistic.normalized_place)),
        func.count(func.distinct(IncidentStatistic.type)),
    ).one()
    rows = (
        base_query.with_entities(IncidentStatistic, Company.name)
        .order_by(
            IncidentStatistic.total_count.desc(),
            IncidentStatistic.updated_at.desc(),
            IncidentStatistic.place.asc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    agents = (
        db_session.query(Company.id, Company.name)
        .join(IncidentStatistic, IncidentStatistic.company_id == Company.id)
        .distinct()
        .order_by(Company.name.asc())
        .all()
    )
    return IncidentStatisticsPageResponse(
        items=[build_incident_statistic_response(row, company_name) for row, company_name in rows],
        total=total,
        page=page,
        page_size=page_size,
        summary=IncidentStatisticsSummary(total_reports=int(total_reports), places=places, categories=categories),
        agents=[IncidentStatisticsAgent(id=company_id, name=company_name) for company_id, company_name in agents],
    )
