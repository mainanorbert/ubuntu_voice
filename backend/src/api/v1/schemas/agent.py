"""Request and response models for the RAG-grounded agent endpoint."""

from typing import Literal

from pydantic import BaseModel, Field

ChatLanguage = Literal["English", "Swahili", "French"]
ChatHistoryRole = Literal["user", "assistant"]


class ChatHistoryMessage(BaseModel):
    """A recent chat turn used to make follow-up RAG questions contextual."""

    role: ChatHistoryRole = Field(..., description="Speaker for the previous chat turn.")
    content: str = Field(..., min_length=1, max_length=1200, description="Previous message text.")


class AgentChatRequest(BaseModel):
    """Inbound chat payload for a RAG-grounded reply."""

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
    history: list[ChatHistoryMessage] = Field(
        default_factory=list,
        max_length=8,
        description="Recent user/assistant turns sent only for this request to support follow-up questions.",
    )


class AgentChatResponse(BaseModel):
    """Assistant text returned after RAG retrieval and LLM generation."""

    reply: str = Field(..., examples=["According to the policy document, refunds are processed within 7 days..."])
    grounded: bool = Field(
        ...,
        description="True when the reply is based on retrieved knowledge-base chunks; False when the query was out of scope.",
    )
