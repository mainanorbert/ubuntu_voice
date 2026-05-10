"""Tests for selecting documents that should be embedded or retried."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.database import Base
from src.models import Company, Document, User, generate_uuid
from src.services.embedding_pipeline import _pending_document_ids
from src.services.ingestion import (
    DOCUMENT_STATUS_FAILED,
    DOCUMENT_STATUS_PENDING,
    count_pending_documents,
)


def test_failed_documents_are_only_selected_for_explicit_retry() -> None:
    """Manual retry includes failed documents; normal background selection does not."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(id="user_retry", email="owner@example.com")
        company = Company(id=generate_uuid(), name="Retry Co", email="retry@example.com", owner_id=user.id)
        pending_doc = Document(
            id=generate_uuid(),
            company_id=company.id,
            uploaded_by=user.id,
            file_name="pending.pdf",
            file_path=f"storage/{company.id}/pending.pdf",
            file_content="",
            status=DOCUMENT_STATUS_PENDING,
            is_embedded=False,
        )
        failed_doc = Document(
            id=generate_uuid(),
            company_id=company.id,
            uploaded_by=user.id,
            file_name="failed.pdf",
            file_path=f"storage/{company.id}/failed.pdf",
            file_content="",
            status=DOCUMENT_STATUS_FAILED,
            is_embedded=False,
        )
        session.add_all([user, company, pending_doc, failed_doc])
        session.commit()

        assert count_pending_documents(session, company_id=company.id) == 1
        assert count_pending_documents(session, company_id=company.id, include_failed=True) == 2
        assert _pending_document_ids(session, company_id=company.id) == [pending_doc.id]
        assert set(_pending_document_ids(session, company_id=company.id, include_failed=True)) == {
            pending_doc.id,
            failed_doc.id,
        }
