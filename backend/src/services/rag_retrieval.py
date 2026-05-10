"""Low-level RAG retrieval: embed a query and search ``document_chunks`` via pgvector."""

from __future__ import annotations

import logging

from openai import AsyncOpenAI
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.services.cost_monitoring import UsageCharge, usage_charge_from_openrouter_usage

logger = logging.getLogger(__name__)


async def embed_query(
    client: AsyncOpenAI,
    query: str,
    *,
    model: str,
    dimensions: int,
) -> tuple[list[float], UsageCharge | None]:
    """Return the embedding vector and billed usage for a single query string."""
    response = await client.embeddings.create(model=model, input=[query])
    vector = list(response.data[0].embedding)
    if len(vector) != dimensions:
        msg = (
            f"Query embedding dimension mismatch: got {len(vector)}, expected {dimensions}. "
            "Check embedding_model / embedding_dimensions in settings."
        )
        raise ValueError(msg)
    return vector, usage_charge_from_openrouter_usage(getattr(response, "usage", None))


def retrieve_chunks_from_db(
    session: Session,
    *,
    company_id: str,
    query_vector: list[float],
    top_k: int,
) -> list[dict]:
    """Return the ``top_k`` chunks most similar to ``query_vector`` for the given tenant.

    Results are ordered by cosine similarity descending. Each dict contains
    ``content``, ``metadata`` and ``similarity`` (0–1 scale).
    """
    vec_literal = "[" + ",".join(str(float(x)) for x in query_vector) + "]"
    sql = text(
        """
        SELECT
            content,
            metadata,
            1 - (embedding <=> CAST(:qvec AS vector)) AS similarity
        FROM document_chunks
        WHERE company_id = :company_id
        ORDER BY similarity DESC
        LIMIT :top_k
        """
    )
    rows: list[dict] = []
    result = session.execute(sql, {"qvec": vec_literal, "company_id": company_id, "top_k": top_k})
    for row in result.mappings():
        rows.append(dict(row))
    return rows


def build_context_from_chunks(chunks: list[dict]) -> str:
    """Concatenate retrieved chunk texts into a labelled context block for prompt injection."""
    parts = []
    for i, chunk in enumerate(chunks, start=1):
        meta = chunk.get("metadata") or {}
        source = meta.get("file_name", "document")
        parts.append(f"[Source {i}: {source}]\n{chunk['content']}")
    return "\n\n---\n\n".join(parts)
