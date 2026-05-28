"""Classifier-agent pipeline for regional incident statistics."""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

from agents import Agent, OpenAIChatCompletionsModel, Runner
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.database import create_database_engine, create_session_factory
from src.models import IncidentStatistic, generate_uuid
from src.services.conflict_alerts import redact_personal_contact_details
from src.services.openrouter_agent import create_openrouter_async_client

logger = logging.getLogger(__name__)

IncidentType = Literal["Rights Violations", "Displacements", "Casualties", "Severe Hunger"]
ALLOWED_INCIDENT_TYPES = {"Rights Violations", "Displacements", "Casualties", "Severe Hunger"}


class IncidentStatisticRecord(BaseModel):
    """One sanitized incident-statistic row proposed by the classifier agent."""

    place: str = Field(..., min_length=1, max_length=160)
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
) -> IncidentClassifierOutput:
    """Run the classifier agent and return validated incident-statistics JSON."""
    model = OpenAIChatCompletionsModel(model=chat_model, openai_client=async_client)
    classifier_agent = Agent(
        name="Incident Statistics Classifier Agent",
        instructions=(
            "You are a classifier agent. Given user prompt: {user_prompt}, determine whether it contains "
            "incident information that should be stored in an incident statistics database. "
            "Classify only reports involving emergency violence, armed groups, victims, rights violations, "
            "displacement, casualties, or severe hunger. Return JSON only with this shape: "
            '{"should_record": boolean, "records": [{"place": string, "description": string, '
            '"type": "Rights Violations|Displacements|Casualties|Severe Hunger"}]}. '
            "Use only the four allowed type values. Return multiple records when the prompt mentions multiple "
            "places or incident types. Do not return duplicate records for the same place and type. "
            "Description must be a short sanitized summary and must not include names, "
            "phone numbers, emails, account IDs, direct quotes, or sensitive identifying details. "
            "Return should_record=false and records=[] for greetings, general questions, historical questions, "
            "or reports without a concrete place."
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
) -> list[IncidentStatistic]:
    """Persist classifier records by incrementing one count per valid record."""
    if not classifier_output.should_record:
        return []

    changed_rows: list[IncidentStatistic] = []
    seen_keys: set[tuple[str, str]] = set()
    for record in classifier_output.records:
        normalized_place = normalize_incident_place(record.place)
        description = sanitize_incident_description(record.description)
        if not normalized_place or not description or record.type not in ALLOWED_INCIDENT_TYPES:
            continue
        key = (normalized_place, record.type)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        statement = (
            update(IncidentStatistic)
            .where(
                IncidentStatistic.company_id == company_id,
                IncidentStatistic.normalized_place == normalized_place,
                IncidentStatistic.type == record.type,
            )
            .values(
                place=record.place.strip(),
                description=description,
                total_count=IncidentStatistic.total_count + 1,
                updated_at=func.now(),
            )
        )
        result = session.execute(statement)
        if result.rowcount == 0:
            row = IncidentStatistic(
                id=generate_uuid(),
                company_id=company_id,
                place=record.place.strip(),
                normalized_place=normalized_place,
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
                IncidentStatistic.normalized_place == normalized_place,
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
    company_id: str,
    user_prompt: str,
) -> None:
    """Background task that classifies a prompt and stores aggregate statistics."""
    client = create_openrouter_async_client(api_key=openrouter_api_key, base_url=openrouter_base_url)
    try:
        classifier_output = await classify_incident_statistics(
            async_client=client,
            chat_model=chat_model,
            user_prompt=user_prompt,
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
        upsert_incident_statistics(session, company_id=company_id, classifier_output=classifier_output)
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
