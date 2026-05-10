"""ORM models for user identity, tenant companies, document state, and spend tracking."""

import uuid
from decimal import Decimal
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database import Base
from src.core.embedding_vector import EmbeddingVector


def generate_uuid() -> str:
    """Return a new UUID string for primary keys stored as text."""
    return str(uuid.uuid4())


# Must match ``Settings.embedding_dimensions`` default and the DB column width.
EMBEDDING_SCHEMA_DIMENSION = 1536


class User(Base):
    """Locally cached Clerk user identity used by relational data."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class Company(Base):
    """Tenant boundary identified by a globally unique name and contact details."""

    __tablename__ = "companies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class UserSpend(Base):
    """Cumulative spend and token usage totals for a single authenticated user."""

    __tablename__ = "user_spend"

    user_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 6),
        nullable=False,
        default=Decimal("0"),
        server_default="0",
    )
    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Document(Base):
    """Metadata for files uploaded into the ingestion pipeline."""

    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("company_id", "file_name", name="uq_documents_company_file_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    uploaded_by: Mapped[str] = mapped_column(
        Text,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        doc="Legacy text field kept for compatibility; searchable text lives in document_chunks.",
    )
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending", server_default="pending")
    is_embedded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class GuardrailEvent(Base):
    """Audit row for prompts/responses that triggered a safety guardrail.

    Stores both the user message and the assistant reply so reviewers can see
    full context for monitored or blocked interactions (PII leakage, oversized
    prompts, etc.). Access to this table should be restricted to operators.
    """

    __tablename__ = "guardrail_events"
    __table_args__ = (
        Index("ix_guardrail_events_user_id", "user_id"),
        Index("ix_guardrail_events_company_id", "company_id"),
        Index("ix_guardrail_events_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    company_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    event_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Stable identifier for the rule, e.g. 'input_token_limit' or 'output_pii'.",
    )
    action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Outcome of the guardrail decision: 'blocked' or 'monitored'.",
    )
    matched_rules: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        doc="Structured detail about which sub-rules fired (e.g. ['email','kenyan_phone']).",
    )
    prompt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    input_token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class DocumentChunk(Base):
    """Text segment and embedding vector for RAG; tenant-scoped via ``company_id``."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_chunk_index"),
        Index("ix_document_chunks_company_id", "company_id"),
        Index("ix_document_chunks_company_document", "company_id", "document_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    company_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(EmbeddingVector(EMBEDDING_SCHEMA_DIMENSION), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
