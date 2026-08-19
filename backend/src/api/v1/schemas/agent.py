"""Request and response models for the RAG-grounded agent endpoint."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError

from src.api.v1.schemas.text_validation import reject_control_characters

ChatLanguage = Literal["English", "Swahili", "French", "Arabic", "Portuguese"]
ChatHistoryRole = Literal["user", "assistant"]


class ReportLocation(BaseModel):
    """A browser-provided location used only to place a report on the map."""

    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy_m: float = Field(..., ge=0, le=100_000)


class ChatHistoryMessage(BaseModel):
    """A recent chat turn used to make follow-up RAG questions contextual."""

    role: ChatHistoryRole = Field(..., description="Speaker for the previous chat turn.")
    content: str = Field(..., min_length=1, max_length=1200, description="Previous message text.")

    @field_validator("content")
    @classmethod
    def validate_content_characters(cls, value: str) -> str:
        """Keep chat history safe for prompt construction and logging."""
        return reject_control_characters(value, allow_formatting=True)


class AgentChatRequest(BaseModel):
    """Inbound chat payload for a RAG-grounded reply."""

    company_id: str = Field(
        ...,
        min_length=1,
        description="Tenant company whose embedded documents are searched for context.",
        examples=["a1b2c3d4-0000-0000-0000-000000000000"],
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User message, limited to 2,000 characters.",
        examples=["What is the refund policy?"],
    )

    @field_validator("message", mode="before")
    @classmethod
    def validate_message_length(cls, value: str) -> str:
        """Return a user-facing prompt-specific length error."""
        if isinstance(value, str) and len(value) > 2000:
            raise PydanticCustomError(
                "prompt_too_long",
                "Prompt should have at most 2000 characters",
            )
        return value

    @field_validator("message")
    @classmethod
    def validate_message_characters(cls, value: str) -> str:
        """Allow readable chat formatting but reject unsafe control characters."""
        return reject_control_characters(value, allow_formatting=True)
    language: ChatLanguage = Field(
        default="English",
        description="Primary language the assistant must use when answering.",
        examples=["English", "Swahili", "French", "Arabic", "Portuguese"],
    )
    history: list[ChatHistoryMessage] = Field(
        default_factory=list,
        max_length=8,
        description="Recent user/assistant turns sent only for this request to support follow-up questions.",
    )
    location: ReportLocation | None = Field(
        default=None,
        description="Optional current browser location. It never prevents a chat reply when absent.",
    )


class AgentChatResponse(BaseModel):
    """Assistant text returned after RAG retrieval and LLM generation."""

    reply: str = Field(..., examples=["According to the policy document, refunds are processed within 7 days..."])
    grounded: bool = Field(
        ...,
        description="True when the reply is based on retrieved knowledge-base chunks; False when the query was out of scope.",
    )
