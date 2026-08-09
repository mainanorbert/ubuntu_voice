"""Tests for server-bound direct-upload confirmation tickets."""

import asyncio

import pytest
from fastapi import BackgroundTasks, HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session


MINIMAL_PDF_BYTES = b"%PDF-1.4 direct upload test"


def test_direct_upload_confirmation_replay_keeps_the_stored_object(tmp_path, monkeypatch):
    """Replaying one ticket returns its document without deleting its object."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("EIVEN_SERVICE_URL", f"sqlite:///{tmp_path / 'direct-upload.db'}")
    monkeypatch.setenv("UPLOAD_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("SUPABASE_URL", "https://storage.example.test")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")

    from src.api.v1.routers import companies as companies_router
    from src.api.v1.schemas.ingestion import DocumentConfirmRequest, DocumentUploadsRequest
    from src.core.auth import UserIdentity
    from src.core.config import Settings
    from src.core.database import Base
    from src.core.dependencies import clear_database_caches
    from src.models import Company, User, generate_uuid

    clear_database_caches()
    deleted_paths: list[str] = []
    verified_paths: list[str] = []

    async def fake_create_signed_upload_url(*, settings, file_path):
        return f"https://storage.example.test/upload/{file_path}"

    async def fake_head_object(*, settings, file_path):
        verified_paths.append(file_path)
        return len(MINIMAL_PDF_BYTES)

    async def fake_download_prefix(*, settings, file_path, length):
        return MINIMAL_PDF_BYTES[:length]

    async def fake_delete_file(*, settings, file_path):
        deleted_paths.append(file_path)

    monkeypatch.setattr(companies_router, "create_supabase_signed_upload_url", fake_create_signed_upload_url)
    monkeypatch.setattr(companies_router, "head_supabase_object", fake_head_object)
    monkeypatch.setattr(companies_router, "download_file_prefix_from_supabase", fake_download_prefix)
    monkeypatch.setattr(companies_router, "delete_stored_document_file", fake_delete_file)

    settings = Settings()
    identity = UserIdentity(user_id="direct_upload_user", email="owner@example.com")
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    company_id = generate_uuid()
    try:
        with Session(engine) as session:
            session.add(User(id=identity.user_id, email=identity.email))
            session.add(
                Company(
                    id=company_id,
                    name="Direct Upload Test Co",
                    email="direct-upload@example.com",
                    owner_id=identity.user_id,
                )
            )
            session.commit()

        with Session(engine) as session:
            minted = asyncio.run(
                companies_router.post_company_document_uploads(
                    company_id=company_id,
                    payload=DocumentUploadsRequest(
                        files=[
                            {
                                "file_name": "guide.pdf",
                                "file_size": len(MINIMAL_PDF_BYTES),
                                "content_type": "application/pdf",
                            }
                        ]
                    ),
                    session_state=identity,
                    settings=settings,
                    db_session=session,
                )
            )
        ticket = minted.uploads[0]
        with Session(engine) as session:
            conflicting_mint = asyncio.run(
                companies_router.post_company_document_uploads(
                    company_id=company_id,
                    payload=DocumentUploadsRequest(
                        files=[
                            {
                                "file_name": "guide.pdf",
                                "file_size": len(MINIMAL_PDF_BYTES),
                                "content_type": "application/pdf",
                            }
                        ]
                    ),
                    session_state=identity,
                    settings=settings,
                    db_session=session,
                )
            )
        conflicting_ticket = conflicting_mint.uploads[0]
        confirmation = DocumentConfirmRequest(
            documents=[
                {
                    "document_id": ticket.document_id,
                    "file_path": ticket.file_path,
                    "file_name": ticket.file_name,
                    "content_type": ticket.content_type,
                }
            ]
        )

        with Session(engine) as session:
            initial_response = Response(status_code=201)
            first_confirmation = asyncio.run(
                companies_router.post_company_document_confirm(
                    company_id=company_id,
                    payload=confirmation,
                    session_state=identity,
                    settings=settings,
                    db_session=session,
                    background_tasks=BackgroundTasks(),
                    response=initial_response,
                )
            )
            assert initial_response.status_code == 201

        with Session(engine) as session:
            replay_response = Response(status_code=201)
            replay_confirmation = asyncio.run(
                companies_router.post_company_document_confirm(
                    company_id=company_id,
                    payload=confirmation,
                    session_state=identity,
                    settings=settings,
                    db_session=session,
                    background_tasks=BackgroundTasks(),
                    response=replay_response,
                )
            )
            assert replay_response.status_code == 200
            assert replay_confirmation == first_confirmation
            assert deleted_paths == []

        conflicting_confirmation = DocumentConfirmRequest(
            documents=[
                {
                    "document_id": conflicting_ticket.document_id,
                    "file_path": conflicting_ticket.file_path,
                    "file_name": conflicting_ticket.file_name,
                    "content_type": conflicting_ticket.content_type,
                }
            ]
        )
        with Session(engine) as session, pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                companies_router.post_company_document_confirm(
                    company_id=company_id,
                    payload=conflicting_confirmation,
                    session_state=identity,
                    settings=settings,
                    db_session=session,
                    background_tasks=BackgroundTasks(),
                    response=Response(status_code=201),
                )
            )
        assert exc_info.value.status_code == 409
        assert deleted_paths == []
        assert verified_paths == [ticket.file_path, conflicting_ticket.file_path]

        tampered_confirmation = DocumentConfirmRequest(
            documents=[
                {
                    "document_id": ticket.document_id,
                    "file_path": ticket.file_path,
                    "file_name": "other.pdf",
                    "content_type": ticket.content_type,
                }
            ]
        )
        with Session(engine) as session, pytest.raises(HTTPException) as exc_info:
            asyncio.run(
                companies_router.post_company_document_confirm(
                    company_id=company_id,
                    payload=tampered_confirmation,
                    session_state=identity,
                    settings=settings,
                    db_session=session,
                    background_tasks=BackgroundTasks(),
                    response=Response(status_code=201),
                )
            )
        assert exc_info.value.status_code == 400
    finally:
        clear_database_caches()
