"""Classifier-agent pipeline for regional incident statistics."""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

import httpx
from agents import Agent, OpenAIChatCompletionsModel, Runner
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import and_, func, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.database import create_database_engine, create_session_factory
from src.models import IncidentStatistic, KnownPlace, generate_uuid
from src.services.conflict_alerts import redact_personal_contact_details
from src.services.openrouter_agent import create_openrouter_async_client

logger = logging.getLogger(__name__)

APPROXIMATE_LOCATION_LABEL = "Approximate current location"
GEOCODING_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"
GEOCODING_COMPONENT_PRIORITY = (
    "locality",
    "sublocality_level_1",
    "sublocality",
    "neighborhood",
    "administrative_area_level_2",
    "administrative_area_level_1",
    "country",
)

IncidentType = Literal["Rights Violations", "Displacements", "Casualties", "Severe Hunger"]
ALLOWED_INCIDENT_TYPES = {"Rights Violations", "Displacements", "Casualties", "Severe Hunger"}


class IncidentLocation(BaseModel):
    """Validated location context supplied by the web chat client."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_m: float = Field(..., ge=0, le=100_000)


def _rounded_coordinate(value: float) -> Decimal:
    """Store an approximately 100-metre grid position rather than raw GPS."""
    return Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def _location_values(
    session: Session, *, normalized_place: str, location: IncidentLocation | None
) -> dict[str, object]:
    """Prefer browser GPS; otherwise resolve the report's named known place."""
    if location is not None:
        latitude = _rounded_coordinate(location.latitude)
        longitude = _rounded_coordinate(location.longitude)
        return {
            "known_place_id": None,
            "latitude": latitude,
            "longitude": longitude,
            "location_accuracy_m": min(100_000, round(location.accuracy_m)),
            "location_source": "gps",
            "location_key": f"gps:{latitude:.3f}:{longitude:.3f}",
        }

    known_place = (
        session.query(KnownPlace)
        .filter(func.lower(func.trim(KnownPlace.name)) == normalized_place, KnownPlace.is_active.is_(True))
        .one_or_none()
    )
    if known_place is not None:
        return {
            "known_place_id": known_place.id,
            "latitude": known_place.latitude,
            "longitude": known_place.longitude,
            "location_accuracy_m": None,
            "location_source": "known_place",
            "location_key": f"known-place:{known_place.id}",
        }
    return {
        "known_place_id": None,
        "latitude": None,
        "longitude": None,
        "location_accuracy_m": None,
        "location_source": "unmapped",
        "location_key": f"place:{normalized_place}",
    }


class IncidentStatisticRecord(BaseModel):
    """One sanitized incident-statistic row proposed by the classifier agent."""

    place: str | None = Field(default=None, max_length=160)
    description: str = Field(..., min_length=1, max_length=500)
    type: IncidentType


class IncidentClassifierOutput(BaseModel):
    """Strict JSON contract returned by the incident-statistics classifier."""

    should_record: bool
    records: list[IncidentStatisticRecord] = Field(default_factory=list, max_length=12)


def normalize_incident_place(place: str) -> str:
    """Normalize a place name for case-insensitive per-region matching."""
    return re.sub(r"\s+", " ", place.strip().casefold())


def sanitize_incident_description(description: str) -> str:
    """Remove obvious personal details from classifier-provided summaries."""
    sanitized = redact_personal_contact_details(description)
    return re.sub(r"\s+", " ", sanitized).strip()[:500]


def select_short_place_name(payload: dict) -> str | None:
    """Select the shortest useful locality from a Google geocoding response."""
    candidates: dict[str, str] = {}
    for result in payload.get("results", []):
        if not isinstance(result, dict):
            continue
        for component in result.get("address_components", []):
            if not isinstance(component, dict):
                continue
            name = component.get("long_name")
            types = component.get("types", [])
            if isinstance(name, str) and name.strip() and isinstance(types, list):
                for component_type in types:
                    if component_type in GEOCODING_COMPONENT_PRIORITY and component_type not in candidates:
                        candidates[component_type] = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()[:160]
    for component_type in GEOCODING_COMPONENT_PRIORITY:
        if candidates.get(component_type):
            return candidates[component_type]
    return None


async def reverse_geocode_short_place_name(
    *, api_key: str, latitude: Decimal, longitude: Decimal
) -> str | None:
    """Best-effort lookup of a locality label; never raises into chat processing."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=1.0)) as client:
            response = await client.get(
                GEOCODING_ENDPOINT,
                params={"latlng": f"{latitude},{longitude}", "key": api_key},
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != "OK":
                logger.info("Reverse geocoding returned status=%s", payload.get("status"))
                return None
            return select_short_place_name(payload)
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        logger.warning("Reverse geocoding failed: error=%s", exc.__class__.__name__)
        return None


async def enrich_gps_statistic_places(
    *, session: Session, company_id: str, location: IncidentLocation, api_key: str | None
) -> None:
    """Replace fallback GPS labels after persistence without changing aggregation keys."""
    if not api_key:
        return
    latitude = _rounded_coordinate(location.latitude)
    longitude = _rounded_coordinate(location.longitude)
    location_key = f"gps:{latitude:.3f}:{longitude:.3f}"
    already_named = (
        session.query(IncidentStatistic.id)
        .filter(
            IncidentStatistic.company_id == company_id,
            IncidentStatistic.location_key == location_key,
            IncidentStatistic.place != APPROXIMATE_LOCATION_LABEL,
            IncidentStatistic.normalized_place == "",
        )
        .first()
    )
    if already_named is not None:
        return
    place_name = await reverse_geocode_short_place_name(api_key=api_key, latitude=latitude, longitude=longitude)
    if not place_name:
        return
    session.query(IncidentStatistic).filter(
        IncidentStatistic.company_id == company_id,
        IncidentStatistic.location_key == location_key,
        IncidentStatistic.place == APPROXIMATE_LOCATION_LABEL,
        IncidentStatistic.normalized_place == "",
    ).update({"place": place_name, "updated_at": func.now()}, synchronize_session=False)
    session.commit()


def parse_incident_classifier_json(raw_output: str) -> IncidentClassifierOutput:
    """Parse and validate raw classifier JSON from a model response."""
    try:
        parsed = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        raise ValueError("Incident classifier returned malformed JSON.") from exc
    try:
        return IncidentClassifierOutput.model_validate(parsed)
    except ValidationError as exc:
        raise ValueError("Incident classifier returned invalid fields.") from exc


async def classify_incident_statistics(
    *,
    async_client: AsyncOpenAI,
    chat_model: str,
    user_prompt: str,
    location_available: bool = False,
) -> IncidentClassifierOutput:
    """Run the classifier agent and return validated incident-statistics JSON."""
    model = OpenAIChatCompletionsModel(model=chat_model, openai_client=async_client)
    location_instruction = (
        "The browser supplied a current location, so an incident report without a named place may be recorded; "
        'use \"place\": null in that case. '
        if location_available
        else "Return should_record=false and records=[] for reports without a concrete place. "
    )
    classifier_agent = Agent(
        name="Incident Statistics Classifier Agent",
        instructions=(
            "You are a classifier agent. Given user prompt: {user_prompt}, determine whether it contains "
            "incident information that should be stored in an incident statistics database. "
            "Classify only reports involving emergency violence, armed groups, victims, rights violations, "
            "displacement, casualties, or severe hunger. Return JSON only with this shape: "
            '{"should_record": boolean, "records": [{"place": string|null, "description": string, '
            '"type": "Rights Violations|Displacements|Casualties|Severe Hunger"}]}. '
            "Use only the four allowed type values. Return multiple records when the prompt mentions multiple "
            "places or incident types. Do not return duplicate records for the same place and type. "
            "Description must be a short sanitized summary and must not include names, "
            "phone numbers, emails, account IDs, direct quotes, or sensitive identifying details. "
            "Return should_record=false and records=[] for greetings, general questions, historical questions, "
            f"or reports without a concrete place. {location_instruction}"
        ),
        model=model,
        output_type=IncidentClassifierOutput,
    )
    result = await Runner.run(classifier_agent, f"User prompt:\n{user_prompt}", max_turns=2)
    return result.final_output_as(IncidentClassifierOutput)


def upsert_incident_statistics(
    session: Session,
    *,
    company_id: str,
    classifier_output: IncidentClassifierOutput,
    location: IncidentLocation | None = None,
) -> list[IncidentStatistic]:
    """Persist classifier records by incrementing one count per valid record."""
    if not classifier_output.should_record:
        return []

    changed_rows: list[IncidentStatistic] = []
    seen_keys: set[tuple[str, str]] = set()
    for record in classifier_output.records:
        reported_place = record.place.strip() if record.place else ""
        normalized_place = normalize_incident_place(reported_place) if reported_place else ""
        description = sanitize_incident_description(record.description)
        if not description or record.type not in ALLOWED_INCIDENT_TYPES:
            continue
        if location is None and not normalized_place:
            continue
        location_values = _location_values(session, normalized_place=normalized_place, location=location)
        key = (str(location_values["location_key"]), record.type)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        display_place = reported_place or APPROXIMATE_LOCATION_LABEL
        stored_normalized_place = "" if location is not None else normalized_place

        location_match = or_(
            IncidentStatistic.location_key == location_values["location_key"],
            and_(
                IncidentStatistic.location_key == "",
                IncidentStatistic.normalized_place == normalized_place,
            ),
        )
        update_values: dict[str, object] = {
            "normalized_place": stored_normalized_place,
            "description": description,
            "total_count": IncidentStatistic.total_count + 1,
            "updated_at": func.now(),
            **location_values,
        }
        # Preserve an explicit user-reported place when a later report only
        # supplies GPS; the geocoder is responsible for fallback labels.
        if reported_place:
            update_values["place"] = reported_place
        statement = (
            update(IncidentStatistic)
            .where(
                IncidentStatistic.company_id == company_id,
                location_match,
                IncidentStatistic.type == record.type,
            )
            .values(**update_values)
        )
        result = session.execute(statement)
        if result.rowcount == 0:
            row = IncidentStatistic(
                id=generate_uuid(),
                company_id=company_id,
                place=display_place,
                normalized_place=stored_normalized_place,
                **location_values,
                description=description,
                type=record.type,
                total_count=1,
            )
            session.add(row)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                session.execute(statement)
                session.commit()
        else:
            session.commit()

        changed_row = (
            session.query(IncidentStatistic)
            .filter(
                IncidentStatistic.company_id == company_id,
                location_match,
                IncidentStatistic.type == record.type,
            )
            .one()
        )
        changed_rows.append(changed_row)
    return changed_rows


async def classify_and_store_incident_statistics(
    *,
    database_url: str,
    openrouter_api_key: str,
    openrouter_base_url: str,
    chat_model: str,
    google_maps_api_key: str | None = None,
    company_id: str,
    user_prompt: str,
    location: IncidentLocation | None = None,
) -> None:
    """Background task that classifies a prompt and stores aggregate statistics."""
    client = create_openrouter_async_client(api_key=openrouter_api_key, base_url=openrouter_base_url)
    try:
        classifier_output = await classify_incident_statistics(
            async_client=client,
            chat_model=chat_model,
            user_prompt=user_prompt,
            location_available=location is not None,
        )
    except Exception as exc:  # noqa: BLE001 - statistics must never block chat.
        logger.warning(
            "Incident statistics classification failed: company_id=%s error=%s",
            company_id,
            exc.__class__.__name__,
        )
        await client.close()
        return

    engine = create_database_engine(database_url)
    factory = create_session_factory(engine)
    session = factory()
    try:
        upsert_incident_statistics(session, company_id=company_id, classifier_output=classifier_output, location=location)
        if location is not None:
            await enrich_gps_statistic_places(
                session=session,
                company_id=company_id,
                location=location,
                api_key=google_maps_api_key,
            )
    except Exception as exc:  # noqa: BLE001 - best-effort monitoring path.
        session.rollback()
        logger.warning(
            "Incident statistics storage failed: company_id=%s error=%s",
            company_id,
            exc.__class__.__name__,
        )
    finally:
        session.close()
        engine.dispose()
        await client.close()
