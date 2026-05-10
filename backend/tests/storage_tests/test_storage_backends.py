"""Tests for switching document storage between local disk and Supabase."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
import httpx
from fastapi import UploadFile
from starlette.datastructures import Headers

from src.services.document_text import extract_document_text
from src.services.ingestion import store_uploaded_document_file
from src.services.supabase_storage import describe_supabase_http_error


def build_test_settings(
    *,
    upload_root: str,
    supabase_url: str | None = None,
    supabase_service_key: str | None = None,
    supabase_bucket: str = "documents",
) -> SimpleNamespace:
    """Build a lightweight settings object with the attributes the storage layer uses."""
    return SimpleNamespace(
        upload_root=upload_root,
        supabase_url=supabase_url,
        supabase_service_key=supabase_service_key,
        supabase_bucket=supabase_bucket,
    )


def build_upload_file(*, file_name: str, file_bytes: bytes, content_type: str) -> UploadFile:
    """Create an in-memory FastAPI upload file for tests."""
    return UploadFile(
        filename=file_name,
        file=BytesIO(file_bytes),
        headers=Headers({"content-type": content_type}),
    )


def test_describe_supabase_http_error_points_connect_errors_at_endpoint_config() -> None:
    """Explain Supabase DNS/connect failures without leaking configured values."""
    message = describe_supabase_http_error(
        operation="signed-URL request",
        exc=httpx.ConnectError("[Errno -2] Name or service not known"),
    )

    assert "SUPABASE_URL" in message
    assert "Name or service not known" not in message


@pytest.mark.anyio
async def test_store_uploaded_document_file_writes_local_when_supabase_is_disabled(tmp_path: Path) -> None:
    """Store uploads on local disk when no Supabase credentials are configured."""
    settings = build_test_settings(upload_root=str(tmp_path))
    upload_file = build_upload_file(
        file_name="guide.pdf",
        file_bytes=b"%PDF-1.4 local test payload",
        content_type="application/pdf",
    )

    stored = await store_uploaded_document_file(
        settings=settings,
        company_id="company_123",
        document_id="doc_123",
        upload_file=upload_file,
    )

    expected_path = tmp_path / "company_123" / "doc_123_guide.pdf"
    assert stored.file_path == "storage/company_123/doc_123_guide.pdf"
    assert expected_path.read_bytes() == b"%PDF-1.4 local test payload"


@pytest.mark.anyio
async def test_store_uploaded_document_file_uploads_to_supabase_when_configured(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upload bytes to Supabase instead of touching local disk when configured."""
    captured: dict[str, object] = {}

    async def fake_upload_file_bytes_to_supabase(*, settings, file_path, file_bytes, content_type) -> None:
        """Capture the outbound Supabase upload request for assertions."""
        captured["settings"] = settings
        captured["file_path"] = file_path
        captured["file_bytes"] = file_bytes
        captured["content_type"] = content_type

    monkeypatch.setattr(
        "src.services.ingestion.upload_file_bytes_to_supabase",
        fake_upload_file_bytes_to_supabase,
    )

    settings = build_test_settings(
        upload_root=str(tmp_path),
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-role-key",
    )
    upload_file = build_upload_file(
        file_name="guide.pdf",
        file_bytes=b"%PDF-1.4 remote test payload",
        content_type="application/pdf",
    )

    stored = await store_uploaded_document_file(
        settings=settings,
        company_id="company_456",
        document_id="doc_456",
        upload_file=upload_file,
    )

    assert stored.file_path == "storage/company_456/doc_456_guide.pdf"
    assert captured["file_path"] == "storage/company_456/doc_456_guide.pdf"
    assert captured["file_bytes"] == b"%PDF-1.4 remote test payload"
    assert captured["content_type"] == "application/pdf"
    assert not (tmp_path / "company_456" / "doc_456_guide.pdf").exists()


def test_extract_document_text_reads_supabase_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Download PDF bytes from Supabase for text extraction when enabled."""
    captured: dict[str, object] = {}

    def fake_download_file_bytes_from_supabase(*, settings, file_path) -> bytes:
        """Capture the requested file path and return PDF bytes."""
        captured["settings"] = settings
        captured["file_path"] = file_path
        return b"%PDF-1.4 downloaded payload"

    def fake_extract_pdf_bytes(file_bytes: bytes) -> str:
        """Capture the downloaded bytes and return extracted text."""
        captured["file_bytes"] = file_bytes
        return "extracted text"

    monkeypatch.setattr(
        "src.services.document_text.download_file_bytes_from_supabase",
        fake_download_file_bytes_from_supabase,
    )
    monkeypatch.setattr("src.services.document_text._extract_pdf_bytes", fake_extract_pdf_bytes)

    settings = build_test_settings(
        upload_root="/tmp/unused",
        supabase_url="https://example.supabase.co",
        supabase_service_key="service-role-key",
    )

    text = extract_document_text(
        settings=settings,
        upload_root="/tmp/unused",
        file_path="storage/company_789/doc_789_guide.pdf",
        file_name="guide.pdf",
        file_type="application/pdf",
    )

    assert text == "extracted text"
    assert captured["file_path"] == "storage/company_789/doc_789_guide.pdf"
    assert captured["file_bytes"] == b"%PDF-1.4 downloaded payload"
