"""Response models for usage monitoring and spend dashboards."""

from datetime import datetime

from pydantic import BaseModel, Field


class UserSpendResponse(BaseModel):
    """Cumulative spend and token totals for a single authenticated user."""

    user_id: str = Field(..., examples=["user_123"])
    email: str | None = Field(default=None, examples=["owner@example.com"])
    total_cost_usd: float = Field(..., examples=[0.024531])
    total_requests: int = Field(..., examples=[12])
    total_prompt_tokens: int = Field(..., examples=[14567])
    total_completion_tokens: int = Field(..., examples=[2210])
    total_tokens: int = Field(..., examples=[16777])
    updated_at: datetime = Field(...)
