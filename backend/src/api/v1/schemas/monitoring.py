"""Response models for the monitoring dashboard endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.api.v1.schemas.text_validation import reject_control_characters


class GuardrailEventResponse(BaseModel):
    """A single audit row from ``guardrail_events`` shaped for dashboard display."""

    id: str
    user_id: str | None = Field(default=None)
    company_id: str | None = Field(default=None)
    event_type: str = Field(
        ...,
        description="Stable rule identifier, e.g. 'input_token_limit' or 'output_pii'.",
    )
    action: str = Field(..., description="'blocked' or 'monitored'.")
    matched_rules: list[str] = Field(default_factory=list)
    prompt_text: str | None = Field(default=None)
    response_text: str | None = Field(default=None)
    input_token_count: int | None = Field(default=None)
    created_at: datetime


class IncidentStatisticResponse(BaseModel):
    """One aggregated incident-statistics row for dashboard display."""

    id: str
    company_id: str
    company_name: str
    place: str
    description: str
    type: str
    total_count: int
    latitude: float | None
    longitude: float | None
    location_source: Literal["gps", "known_place", "unmapped"]
    known_place_id: int | None
    location_key: str
    updated_at: datetime


class IncidentStatisticUpdate(BaseModel):
    """Validated corrections to one aggregated incident-statistics row."""

    place: str = Field(..., min_length=1, max_length=160)
    description: str = Field(..., min_length=1, max_length=500)
    type: Literal["Rights Violations", "Displacements", "Casualties", "Severe Hunger"]
    total_count: int = Field(..., ge=1, le=1_000_000_000)

    @field_validator("place")
    @classmethod
    def validate_place_characters(cls, value: str) -> str:
        return reject_control_characters(value)


class IncidentStatisticsSummary(BaseModel):
    """Aggregate values for the currently selected incident-statistics filter."""

    total_incidents: int
    places: int
    categories: int


class IncidentStatisticsAgent(BaseModel):
    """An agent that has reported at least one incident statistic."""

    id: str
    name: str


class IncidentStatisticsPageResponse(BaseModel):
    """A paginated, authenticated view of incident statistics."""

    items: list[IncidentStatisticResponse]
    total: int
    page: int
    page_size: int
    summary: IncidentStatisticsSummary
    agents: list[IncidentStatisticsAgent]


class KnownPlaceResponse(BaseModel):
    id: int
    name: str
    country: str | None
    latitude: float
    longitude: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class KnownPlaceInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    country: str | None = Field(default=None, max_length=100)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    @field_validator("name")
    @classmethod
    def validate_name_characters(cls, value: str) -> str:
        return reject_control_characters(value)
