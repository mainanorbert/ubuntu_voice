"""Request and response schemas for independent RAG evaluations."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

EvaluationStatus = Literal["pending", "running", "completed", "partial", "failed"]


class EvaluationQuestionCreate(BaseModel):
    """One editable question and its expected reference answer."""

    question: str = Field(..., min_length=1, max_length=4000)
    reference_answer: str = Field(..., min_length=1, max_length=8000)

    @field_validator("question", "reference_answer")
    @classmethod
    def reject_blank_text(cls, value: str) -> str:
        """Trim evaluation text and reject whitespace-only values."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Evaluation text cannot be blank.")
        return trimmed


class EvaluationQuestionResponse(BaseModel):
    """Stored question in an agent-specific evaluation dataset."""

    id: str
    question: str
    reference_answer: str
    created_at: datetime


class RetrievedSourceResponse(BaseModel):
    """Non-sensitive metadata describing one retrieved source."""

    source: str
    similarity: float


class EvaluationResultResponse(BaseModel):
    """Detailed outcome for one evaluated question."""

    id: str
    question: str
    reference_answer: str
    generated_answer: str
    retrieved_sources: list[RetrievedSourceResponse]
    correctness_passed: bool | None
    correctness_explanation: str | None
    relevance_passed: bool | None
    relevance_explanation: str | None
    groundedness_passed: bool | None
    groundedness_explanation: str | None
    retrieval_relevance_passed: bool | None
    retrieval_relevance_explanation: str | None
    operational_error: str | None


class EvaluationRunResponse(BaseModel):
    """Latest evaluation run and its completed per-question results."""

    id: str
    status: EvaluationStatus
    total_questions: int
    completed_questions: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    results: list[EvaluationResultResponse]


class EvaluationWorkspaceResponse(BaseModel):
    """Selected agent's editable dataset and retained latest run."""

    questions: list[EvaluationQuestionResponse]
    latest_run: EvaluationRunResponse | None
