"""Extract plain text from uploaded files stored locally or in Supabase."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from src.core.config import Settings
from src.services.supabase_storage import download_file_bytes_from_supabase, uses_supabase_storage


class UnsupportedDocumentFormatError(ValueError):
    """Raised when a file type is not supported for text extraction."""


def resolve_stored_document_path(*, upload_root: str, file_path: str) -> Path:
    """Map a DB ``file_path`` (``storage/{company_id}/…``) to an absolute ``Path``."""
    prefix = "storage/"
    if not file_path.startswith(prefix):
        msg = f"Unexpected file_path format (expected '{prefix}' prefix): {file_path!r}"
        raise ValueError(msg)
    relative_under_root = file_path[len(prefix) :].lstrip("/")
    return Path(upload_root).expanduser().resolve() / relative_under_root


def extract_document_text(
    *,
    settings: Settings,
    upload_root: str,
    file_path: str,
    file_name: str,
    file_type: str | None,
) -> str:
    """Read a stored PDF upload and return UTF-8 text suitable for chunking.

    Only PDF files are supported. Any other format raises ``UnsupportedDocumentFormatError``.
    """
    suffix = Path(file_name).suffix.lower()
    mime = (file_type or "").lower()

    if suffix == ".pdf" or "pdf" in mime:
        if uses_supabase_storage(settings):
            file_bytes = download_file_bytes_from_supabase(settings=settings, file_path=file_path)
            return _extract_pdf_bytes(file_bytes)

        path = resolve_stored_document_path(upload_root=upload_root, file_path=file_path)
        if not path.is_file():
            msg = f"Upload file missing on disk: {path}"
            raise FileNotFoundError(msg)
        return _extract_pdf_text(path)

    raise UnsupportedDocumentFormatError(
        f"Only PDF documents are supported for embedding: suffix={suffix!r} mime={mime!r} file={file_name!r}"
    )


def _extract_pdf_text(path: Path) -> str:
    """Return joined text from all pages of a PDF file."""
    reader = PdfReader(str(path))
    return _join_pdf_page_text(reader)


def _extract_pdf_bytes(file_bytes: bytes) -> str:
    """Return joined text from all pages of a PDF file loaded from bytes."""
    reader = PdfReader(BytesIO(file_bytes))
    return _join_pdf_page_text(reader)


def _join_pdf_page_text(reader: PdfReader) -> str:
    """Join extracted text from all non-empty pages in a PDF reader."""
    parts: list[str] = []
    for page in reader.pages:
        extracted = page.extract_text() or ""
        if extracted.strip():
            parts.append(extracted)
    return "\n\n".join(parts).strip()
