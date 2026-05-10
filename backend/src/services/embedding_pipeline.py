"""Background job: extract text, chunk, embed, and persist ``DocumentChunk`` rows."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from src.core.config import Settings
from src.core.database import create_database_engine, create_session_factory
from src.models import Document, DocumentChunk, EMBEDDING_SCHEMA_DIMENSION, User, generate_uuid
from src.services.chunking import chunk_plain_text
from src.services.cost_monitoring import UsageCharge, record_user_spend
from src.services.document_text import UnsupportedDocumentFormatError, extract_document_text
from src.services.embeddings import embed_texts_sync
from src.services.ingestion import (
    DOCUMENT_STATUS_COMPLETED,
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_PROCESSING,
)
from src.services.openrouter_agent import create_openrouter_sync_client
from src.services.supabase_storage import ExternalStorageError

logger = logging.getLogger(__name__)


def run_embedding_pipeline_for_company(
    *,
    database_url: str,
    upload_root: str,
    company_id: str,
    include_failed: bool = False,
) -> None:
    """Embed all non-embedded documents for ``company_id`` and write ``document_chunks``.

    Uses a fresh SQLAlchemy engine and session so it is safe to run from FastAPI
    ``BackgroundTasks`` after the HTTP request completes. No-ops on non-PostgreSQL
    databases (e.g. SQLite in unit tests) because pgvector storage is not available.
    """
    settings = Settings()
    if settings.embedding_dimensions != EMBEDDING_SCHEMA_DIMENSION:
        logger.error(
            "embedding_dimensions=%s does not match ORM schema dimension %s; skipping pipeline.",
            settings.embedding_dimensions,
            EMBEDDING_SCHEMA_DIMENSION,
        )
        return

    engine = create_database_engine(database_url)
    if engine.dialect.name != "postgresql":
        logger.info("Skipping embedding pipeline: database dialect is not PostgreSQL.")
        return

    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        client = create_openrouter_sync_client(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
        )
        for doc_id in _pending_document_ids(session, company_id=company_id, include_failed=include_failed):
            document = session.get(Document, doc_id)
            if document is None or document.is_embedded:
                continue
            try:
                usage_charge = _embed_single_document(
                    session,
                    client=client,
                    settings=settings,
                    upload_root=upload_root,
                    document=document,
                )
                if usage_charge is not None:
                    uploaded_by = session.get(User, document.uploaded_by)
                    record_user_spend(
                        session,
                        user_id=document.uploaded_by,
                        email=None if uploaded_by is None else uploaded_by.email,
                        charge=usage_charge,
                    )
                session.commit()
            except Exception:
                session.rollback()
                failed = session.get(Document, doc_id)
                if failed is not None:
                    failed.status = DOCUMENT_STATUS_FAILED
                    failed.is_embedded = False
                    session.commit()
                logger.exception("Failed embedding document id=%s", doc_id)
    finally:
        session.close()


def _pending_document_ids(session: Session, *, company_id: str, include_failed: bool = False) -> list[str]:
    """Return primary keys of documents awaiting embeddings for this tenant."""
    query = session.query(Document.id).filter(
        Document.company_id == company_id,
        Document.is_embedded.is_(False),
    )
    if not include_failed:
        query = query.filter(Document.status != DOCUMENT_STATUS_FAILED)
    rows = query.order_by(Document.created_at.asc()).all()
    return [row[0] for row in rows]


def _embed_single_document(
    session: Session,
    *,
    client,
    settings: Settings,
    upload_root: str,
    document: Document,
) -> UsageCharge | None:
    """Extract text for one document, replace chunks, and return billed embedding usage."""
    document.status = DOCUMENT_STATUS_PROCESSING
    session.flush()

    try:
        text = extract_document_text(
            settings=settings,
            upload_root=upload_root,
            file_path=document.file_path,
            file_name=document.file_name,
            file_type=document.file_type,
        )
    except UnsupportedDocumentFormatError as exc:
        logger.warning("Document %s not embedded: %s", document.id, exc)
        document.status = DOCUMENT_STATUS_FAILED
        document.is_embedded = False
        session.flush()
        return None
    except (ExternalStorageError, OSError, FileNotFoundError, ValueError) as exc:
        logger.warning("Document %s extraction error: %s", document.id, exc)
        document.status = DOCUMENT_STATUS_FAILED
        document.is_embedded = False
        session.flush()
        return None

    if not text.strip():
        logger.warning("Document %s has empty text after extraction; marking failed.", document.id)
        document.status = DOCUMENT_STATUS_FAILED
        document.is_embedded = False
        session.flush()
        return None

    chunk_rows = chunk_plain_text(
        text,
        max_chars=settings.embedding_max_chars_per_chunk,
        overlap_chars=settings.embedding_chunk_overlap_chars,
        file_name=document.file_name,
    )

    session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete(synchronize_session=False)

    if not chunk_rows:
        logger.warning("Document %s produced zero chunks; marking failed.", document.id)
        document.status = DOCUMENT_STATUS_FAILED
        document.is_embedded = False
        session.flush()
        return None

    chunk_texts = [content for _index, content, _meta in chunk_rows]
    vectors, usage_charge = embed_texts_sync(
        client,
        chunk_texts,
        model=settings.embedding_model,
        expected_dimensions=settings.embedding_dimensions,
        batch_size=settings.embedding_api_batch_size,
    )

    for (chunk_index, content, meta), vector in zip(chunk_rows, vectors, strict=True):
        row = DocumentChunk(
            id=generate_uuid(),
            company_id=document.company_id,
            document_id=document.id,
            content=content,
            embedding=vector,
            chunk_index=chunk_index,
            chunk_metadata=meta,
        )
        session.add(row)

    document.is_embedded = True
    document.status = DOCUMENT_STATUS_COMPLETED
    session.flush()
    return usage_charge
