"""Services for user sync, tenant setup, and document file ingestion."""

from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.core.config import Settings
from src.models import Company, Document, User, generate_uuid
from src.services.supabase_storage import delete_file_from_supabase, upload_file_bytes_to_supabase, uses_supabase_storage

DOCUMENT_STATUS_PENDING = "pending"
DOCUMENT_STATUS_PROCESSING = "processing"
DOCUMENT_STATUS_COMPLETED = "completed"
DOCUMENT_STATUS_FAILED = "failed"

# Hard ceiling for any single PDF, applied both to multipart and signed-URL flows.
# Tuned for a free-tier deployment talking to Supabase Storage from a browser.
MAX_PDF_UPLOAD_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class StoredDocumentFile:
    """Metadata captured after persisting an uploaded file to durable storage."""

    file_name: str
    file_path: str
    file_size: int
    file_type: str | None


def upsert_user(session: Session, *, user_id: str, email: str | None) -> tuple[User, bool]:
    """Create or refresh the local user record that mirrors Clerk identity."""
    user = session.get(User, user_id)
    if user is None:
        user = User(id=user_id, email=email)
        session.add(user)
        session.flush()
        return user, True

    if email and user.email != email:
        user.email = email
        session.flush()

    return user, False


def get_or_create_company(
    session: Session,
    *,
    owner_id: str,
    name: str,
    email: str,
    phone: str | None,
    description: str | None,
) -> tuple[Company, bool]:
    """Return the company matching the given email, creating it if it does not exist.

    Returns a (company, created) tuple where created is True when a new row was inserted.
    If the email already belongs to another owner the existing company is returned as-is.
    """
    normalized_email = email.strip().lower()
    existing = session.query(Company).filter(Company.email == normalized_email).one_or_none()
    if existing is not None:
        if phone and not existing.phone:
            existing.phone = phone
        if description and not existing.description:
            existing.description = description
        session.flush()
        return existing, False

    normalized_name = name.strip()
    if not normalized_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company name cannot be empty.")

    company = Company(
        name=normalized_name,
        email=normalized_email,
        phone=phone,
        description=description,
        owner_id=owner_id,
    )
    session.add(company)
    session.flush()
    return company, True


def list_companies_for_owner(session: Session, *, owner_id: str) -> list[Company]:
    """Return companies owned by the provided user id."""
    return (
        session.query(Company)
        .filter(Company.owner_id == owner_id)
        .order_by(Company.created_at.desc())
        .all()
    )


def get_owned_company(session: Session, *, company_id: str, owner_id: str) -> Company:
    """Return the requested company only if it belongs to the authenticated owner."""
    company = (
        session.query(Company)
        .filter(Company.id == company_id, Company.owner_id == owner_id)
        .one_or_none()
    )
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")
    return company


def list_documents(session: Session, *, company_id: str) -> list[Document]:
    """Return ingested documents for a company sorted from newest to oldest."""
    return (
        session.query(Document)
        .filter(Document.company_id == company_id)
        .order_by(Document.created_at.desc())
        .all()
    )


def count_pending_documents(session: Session, *, company_id: str, include_failed: bool = False) -> int:
    """Return the number of documents awaiting embedding for the given company.

    Counts rows where ``is_embedded`` is false. Failed rows are included only
    for explicit retry flows.
    """
    query = session.query(Document).filter(
        Document.company_id == company_id,
        Document.is_embedded.is_(False),
    )
    if not include_failed:
        query = query.filter(Document.status != DOCUMENT_STATUS_FAILED)
    return query.count()


def ensure_document_name_is_available(session: Session, *, company_id: str, file_name: str) -> None:
    """Reject uploads that would violate the per-company file name uniqueness constraint."""
    existing = (
        session.query(Document)
        .filter(Document.company_id == company_id, Document.file_name == file_name)
        .one_or_none()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A document named '{file_name}' already exists for this company.",
        )


def sanitize_file_name(file_name: str) -> str:
    """Remove unsafe path components from an uploaded file name."""
    cleaned_name = Path(file_name).name.strip()
    if not cleaned_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must have a name.")
    if cleaned_name in {".", ".."}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file name is invalid.")
    return cleaned_name


def assert_pdf_upload(upload_file: UploadFile) -> None:
    """Raise HTTP 415 when the uploaded file is not a PDF.

    Checks both the filename extension and the declared MIME type so that
    non-PDF files are rejected before any bytes are written to disk.
    """
    name = upload_file.filename or ""
    mime = (upload_file.content_type or "").lower().strip()
    suffix = Path(name).suffix.lower()

    if suffix != ".pdf" or mime not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Only PDF files are accepted. Received: name={name!r} type={mime!r}.",
        )


def assert_pdf_metadata(*, file_name: str, content_type: str, file_size: int) -> None:
    """Validate metadata sent by the client when minting signed upload URLs.

    Mirrors :func:`assert_pdf_upload` for the signed-upload flow where bytes
    never reach the backend. Also enforces :data:`MAX_PDF_UPLOAD_BYTES`.
    """
    suffix = Path(file_name).suffix.lower()
    mime = (content_type or "").lower().strip()
    if suffix != ".pdf" or mime not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Only PDF files are accepted. Received: name={file_name!r} type={mime!r}.",
        )
    if file_size <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File size must be positive.")
    if file_size > MAX_PDF_UPLOAD_BYTES:
        max_mb = MAX_PDF_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File '{file_name}' is too large. Maximum allowed size is {max_mb} MB.",
        )


def build_storage_relative_path(*, company_id: str, document_id: str, safe_name: str) -> str:
    """Return the canonical ``storage/{company}/{doc}_{name}`` key for a new document."""
    stored_name = f"{document_id}_{safe_name}"
    return f"storage/{company_id}/{stored_name}"


async def store_uploaded_document_file(
    *,
    settings: Settings,
    company_id: str,
    document_id: str,
    upload_file: UploadFile,
) -> StoredDocumentFile:
    """Persist an uploaded file and return the metadata stored in the database.

    The stored path recorded in the database always uses the ``storage/{company_id}/{stored_name}``
    format defined in the schema so the metadata layer remains stable regardless of whether
    the bytes are written to local disk or uploaded to Supabase Storage.
    """
    original_name = upload_file.filename or ""
    safe_name = sanitize_file_name(original_name)
    relative_path = build_storage_relative_path(
        company_id=company_id, document_id=document_id, safe_name=safe_name
    )
    content_type = upload_file.content_type
    file_size = 0
    file_bytes = bytearray()
    while True:
        chunk = await upload_file.read(1024 * 1024)
        if not chunk:
            break
        file_size += len(chunk)
        if file_size > MAX_PDF_UPLOAD_BYTES:
            await upload_file.close()
            max_mb = MAX_PDF_UPLOAD_BYTES // (1024 * 1024)
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File '{safe_name}' is too large. Maximum allowed size is {max_mb} MB.",
            )
        file_bytes.extend(chunk)

    await upload_file.close()

    if file_size == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    if uses_supabase_storage(settings):
        await upload_file_bytes_to_supabase(
            settings=settings,
            file_path=relative_path,
            file_bytes=bytes(file_bytes),
            content_type=content_type,
        )
    else:
        target_directory = Path(settings.upload_root).expanduser().resolve() / company_id
        target_directory.mkdir(parents=True, exist_ok=True)
        # The relative path is "storage/{company_id}/{document_id}_{safe_name}";
        # strip the company prefix to land beneath ``target_directory``.
        destination_path = target_directory / Path(relative_path).name
        destination_path.write_bytes(file_bytes)

    return StoredDocumentFile(
        file_name=safe_name,
        file_path=relative_path,
        file_size=file_size,
        file_type=content_type,
    )


async def delete_stored_document_file(*, settings: Settings, file_path: str) -> None:
    """Delete a previously stored document from the active storage backend."""
    if uses_supabase_storage(settings):
        await delete_file_from_supabase(settings=settings, file_path=file_path)
        return

    relative_path = file_path.removeprefix("storage/").lstrip("/")
    target_path = Path(settings.upload_root).expanduser().resolve() / relative_path
    target_path.unlink(missing_ok=True)


def create_document_record(
    session: Session,
    *,
    document_id: str,
    company_id: str,
    uploaded_by: str,
    stored_file: StoredDocumentFile,
) -> Document:
    """Insert a document metadata record for a file already stored."""
    document = Document(
        id=document_id,
        company_id=company_id,
        uploaded_by=uploaded_by,
        file_name=stored_file.file_name,
        file_path=stored_file.file_path,
        file_content="",
        file_size=stored_file.file_size,
        file_type=stored_file.file_type,
        status=DOCUMENT_STATUS_PENDING,
        is_embedded=False,
    )
    session.add(document)
    session.flush()
    return document
