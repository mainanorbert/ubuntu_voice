"""API tests for tenant document ingestion (file + metadata, pre-embeddings)."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# Minimal well-formed PDF header accepted by assert_pdf_upload
MINIMAL_PDF_BYTES = b"%PDF-1.4 test document"


def test_document_ingestion_persists_pending_metadata(tmp_path, monkeypatch):
    """Upload creates a pending document row, stores bytes on disk, and lists them back."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-clerk-secret")
    db_file = tmp_path / "ingestion.db"
    upload_root = tmp_path / "uploads"

    # EIVEN_SERVICE_URL is read from .env with higher alias priority than DATABASE_URL.
    # Override it in the process environment (env vars beat .env file in pydantic-settings).
    monkeypatch.setenv("EIVEN_SERVICE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("UPLOAD_ROOT", str(upload_root))

    # Disable Supabase storage so uploads go to local disk (avoids network calls in tests).
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")

    from clerk_backend_api.security.types import AuthStatus, RequestState
    from src.core.clerk_auth import require_clerk_session
    from src.core.dependencies import clear_database_caches

    clear_database_caches()

    from src.main import app

    async def stub_require_clerk_session():
        """Return a signed-in Clerk state without calling the Clerk SDK."""
        return RequestState(
            status=AuthStatus.SIGNED_IN,
            token="test-session",
            payload={"sub": "user_ingest_test", "email": "owner@example.com"},
        )

    app.dependency_overrides[require_clerk_session] = stub_require_clerk_session
    try:
        with TestClient(app) as client:
            company_response = client.post(
                "/api/v1/companies",
                json={
                    "name": "Ingestion Test Co",
                    "email": "info@ingestion-test.example",
                    "phone": "+254712345678",
                    "description": "Answers questions from uploaded program documents.",
                },
            )
            assert company_response.status_code == 201, company_response.text
            company_body = company_response.json()
            company_id = company_body["id"]
            assert company_body["phone"] == "+254712345678"
            assert company_body["description"] == "Answers questions from uploaded program documents."

            doc_response = client.post(
                f"/api/v1/companies/{company_id}/documents",
                files={"files": ("handbook.pdf", MINIMAL_PDF_BYTES, "application/pdf")},
            )
            assert doc_response.status_code == 201, doc_response.text
            docs = doc_response.json()
            assert isinstance(docs, list) and len(docs) == 1
            body = docs[0]
            assert body["status"] == "pending"
            assert body["is_embedded"] is False
            assert body["file_name"] == "handbook.pdf"
            assert body["company_id"] == company_id
            assert body["uploaded_by"] == "user_ingest_test"

            # file_path is stored as "storage/{company_id}/..." relative key;
            # the actual file lives under upload_root.
            relative_path = body["file_path"].removeprefix("storage/").lstrip("/")
            stored_path = upload_root / relative_path
            assert stored_path.is_file(), f"Expected file at {stored_path}"
            assert stored_path.read_bytes() == MINIMAL_PDF_BYTES

            list_response = client.get(f"/api/v1/companies/{company_id}/documents")
            assert list_response.status_code == 200
            listed = list_response.json()
            assert len(listed["documents"]) == 1
            assert listed["documents"][0]["id"] == body["id"]
    finally:
        app.dependency_overrides.clear()
        clear_database_caches()
