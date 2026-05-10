#!/usr/bin/env python3
"""Query ``document_chunks`` in Aiven Postgres (pgvector) using a natural-language question.

Run from the ``backend`` directory so imports resolve::

    cd backend
    uv run python tests/query_embeddings.py --company-id <uuid> --query "What is the refund policy?"

Environment (typically in ``backend/.env``): ``EIVEN_SERVICE_URL`` or ``DATABASE_URL``,
``OPENROUTER_API_KEY``, ``OPENROUTER_BASE_URL``, embedding fields from ``Settings``,
``CLERK_SECRET_KEY``, etc.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for company id, query text, and result count."""
    parser = argparse.ArgumentParser(description="Nearest-neighbour search over document_chunks.")
    parser.add_argument(
        "--company-id",
        required=True,
        help="Tenant UUID (same as companies.id / document_chunks.company_id).",
    )
    parser.add_argument(
        "--query",
        required=True,
        help="Natural-language question; embedded with the same model as ingestion.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to return (default: 5).",
    )
    return parser.parse_args()


def load_settings():
    """Load application settings from ``backend/.env`` regardless of cwd."""
    from pydantic_settings import SettingsConfigDict

    from src.core.config import Settings

    class _BackendEnvSettings(Settings):
        model_config = SettingsConfigDict(
            env_file=str(BACKEND_ROOT / ".env"),
            env_file_encoding="utf-8",
            extra="ignore",
        )

    return _BackendEnvSettings()


def build_query_vector(settings, query: str) -> list[float]:
    """Embed the user query with OpenRouter (same API as document ingestion)."""
    from src.services.embeddings import embed_texts_sync
    from src.services.openrouter_agent import create_openrouter_sync_client

    client = create_openrouter_sync_client(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
    )
    vectors = embed_texts_sync(
        client,
        [query],
        model=settings.embedding_model,
        expected_dimensions=settings.embedding_dimensions,
        batch_size=1,
    )
    return vectors[0]


def format_vector_literal(vector: list[float]) -> str:
    """Format a Python float list as a pgvector literal string."""
    inner = ",".join(str(float(x)) for x in vector)
    return f"[{inner}]"


def search_similar_chunks(
    engine: Engine,
    *,
    company_id: str,
    query_vector: list[float],
    top_k: int,
) -> list[dict]:
    """Return the ``top_k`` chunks closest to ``query_vector`` for the given company (cosine distance)."""
    vec_literal = format_vector_literal(query_vector)
    sql = text(
        """
        SELECT
            id,
            document_id,
            chunk_index,
            content,
            metadata,
            embedding <=> CAST(:qvec AS vector) AS distance
        FROM document_chunks
        WHERE company_id = :company_id
        ORDER BY distance
        LIMIT :top_k
        """
    )
    rows: list[dict] = []
    with engine.connect() as conn:
        result = conn.execute(
            sql,
            {"qvec": vec_literal, "company_id": company_id, "top_k": top_k},
        )
        for row in result.mappings():
            rows.append(dict(row))
    return rows


def print_results(rows: list[dict]) -> None:
    """Print retrieved chunks in a readable form."""
    if not rows:
        print("No chunks found for this company_id (empty table or wrong id).")
        return
    for i, row in enumerate(rows, start=1):
        dist = row.get("distance")
        content = (row.get("content") or "").replace("\n", " ").strip()
        preview = content[:400] + ("…" if len(content) > 400 else "")
        print(
            f"\n--- Rank {i}  distance={dist:.6f}  chunk_index={row.get('chunk_index')}  "
            f"doc={row.get('document_id')} ---"
        )
        print(preview)
        meta = row.get("metadata")
        if meta:
            print(f"metadata: {meta}")


def main() -> None:
    """Load settings, embed the query, run vector search, and print results."""
    args = parse_args()
    settings = load_settings()

    engine = create_engine(settings.database_url, future=True)
    if engine.dialect.name != "postgresql":
        print("This script requires PostgreSQL (Aiven) with pgvector.", file=sys.stderr)
        sys.exit(1)

    print(f"Embedding model: {settings.embedding_model} (dim={settings.embedding_dimensions})")
    query_vector = build_query_vector(settings, args.query)
    print(f"Query: {args.query!r}\nSearching company_id={args.company_id!r} …")

    rows = search_similar_chunks(
        engine,
        company_id=args.company_id,
        query_vector=query_vector,
        top_k=args.top_k,
    )
    print_results(rows)


if __name__ == "__main__":
    main()