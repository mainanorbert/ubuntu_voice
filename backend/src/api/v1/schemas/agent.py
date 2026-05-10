"""Request and response models for the RAG-grounded agent endpoint."""

from typing import Literal

from pydantic import BaseModel, Field

ChatLanguage = Literal["English", "Swahili", "French"]


class AgentChatRequest(BaseModel):
    """Inbound chat payload for a RAG-grounded single-turn reply."""

    company_id: str = Field(
        ...,
        min_length=1,
        description="Tenant company whose embedded documents are searched for context.",
        examples=["a1b2c3d4-0000-0000-0000-000000000000"],
    )
    message: str = Field(..., min_length=1, examples=["What is the refund policy?"])
    language: ChatLanguage = Field(
        default="English",
        description="Primary language the assistant must use when answering.",
        examples=["English", "Swahili", "French"],
    )


class AgentChatResponse(BaseModel):
    """Assistant text returned after RAG retrieval and LLM generation."""

    reply: str = Field(..., examples=["According to the policy document, refunds are processed within 7 days..."])
    grounded: bool = Field(
        ...,
        description="True when the reply is based on retrieved knowledge-base chunks; False when the query was out of scope.",
    )
