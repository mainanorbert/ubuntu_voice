"""Response models for the monitoring dashboard endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


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
