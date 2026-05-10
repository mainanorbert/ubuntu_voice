"""Routes for company management and multi-file document ingestion."""
from typing import Annotated

from clerk_backend_api.security.types import RequestState
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.v1.schemas.ingestion import (
    CompanyCreateRequest,
    CompanyResponse,
    CompanyWithDocumentsResponse,
    DocumentConfirmRequest,
    DocumentResponse,
    DocumentUploadsRequest,
    DocumentUploadsResponse,
    DocumentUploadTicket,
    EmbedTriggerResponse,
)
from src.core.clerk_auth import get_authenticated_user_identity, require_clerk_session
from src.core.config import Settings
from src.core.dependencies import get_db_session, get_settings
from src.models import generate_uuid
from src.services.embedding_pipeline import run_embedding_pipeline_for_company
from src.services.ingestion import (
    StoredDocumentFile,
    assert_pdf_metadata,
    assert_pdf_upload,
    build_storage_relative_path,
    count_pending_documents,
    create_document_record,
    delete_stored_document_file,
    ensure_document_name_is_available,
    get_or_create_company,
    get_owned_company,
    list_companies_for_owner,
    list_documents,
    sanitize_file_name,
    store_uploaded_document_file,
    upsert_user,
)
from src.services.supabase_storage import (
    ExternalStorageError,
    create_supabase_signed_upload_url,
    head_supabase_object,
    uses_supabase_storage,
)

router = APIRouter(prefix="/companies", tags=["companies"])


def build_company_response(company) -> CompanyResponse:
    """Serialize a company ORM object into an API response model."""
    return CompanyResponse(
        id=company.id,
        name=company.name,
        email=company.email,
        phone=company.phone,
        owner_id=company.owner_id,
        created_at=company.created_at,
    )


def build_document_response(document) -> DocumentResponse:
    """Serialize a document ORM object into an API response model."""
    return DocumentResponse(
        id=document.id,
        company_id=document.company_id,
        uploaded_by=document.uploaded_by,
        file_name=document.file_name,
        file_path=document.file_path,
        file_size=document.file_size,
        file_type=document.file_type,
        status=document.status,
        is_embedded=document.is_embedded,
        created_at=document.created_at,
    )


@router.get("", response_model=list[CompanyResponse])
async def get_companies(
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> list[CompanyResponse]:
    """List companies owned by the authenticated user."""
    identity = get_authenticated_user_identity(session_state)
    companies = list_companies_for_owner(db_session, owner_id=identity.user_id)
    return [build_company_response(c) for c in companies]


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def post_company(
    body: CompanyCreateRequest,
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> CompanyResponse:
    """Create or retrieve a company for the authenticated user by email.

    If a company with the given email already exists it is returned unchanged.
    A new company is created when the email has not been registered before.
    """
    identity = get_authenticated_user_identity(session_state)
    user, _created = upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    company, _new = get_or_create_company(
        db_session,
        owner_id=user.id,
        name=body.name,
        email=str(body.email),
        phone=body.phone,
    )
    db_session.commit()
    db_session.refresh(company)
    return build_company_response(company)


@router.get("/{company_id}/documents", response_model=CompanyWithDocumentsResponse)
async def get_company_documents(
    company_id: str,
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> CompanyWithDocumentsResponse:
    """Return the authenticated owner's company plus its current document list."""
    identity = get_authenticated_user_identity(session_state)
    company = get_owned_company(db_session, company_id=company_id, owner_id=identity.user_id)
    documents = list_documents(db_session, company_id=company.id)
    return CompanyWithDocumentsResponse(
        company=build_company_response(company),
        documents=[build_document_response(d) for d in documents],
    )


@router.post(
    "/{company_id}/documents",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def post_company_documents(
    company_id: str,
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
    background_tasks: BackgroundTasks,
    files: Annotated[list[UploadFile], File(...)],
) -> list[DocumentResponse]:
    """Store one or more uploaded documents and persist their metadata.

    Each file is validated for a unique name within the company before being stored.
    All files are processed in a single database transaction; if any insert fails the
    transaction is rolled back and all already-stored files are removed.
    """
    identity = get_authenticated_user_identity(session_state)
    user, _created = upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    company = get_owned_company(db_session, company_id=company_id, owner_id=user.id)

    for upload_file in files:
        assert_pdf_upload(upload_file)

    safe_names = [sanitize_file_name(f.filename or "") for f in files]
    for safe_name in safe_names:
        ensure_document_name_is_available(db_session, company_id=company.id, file_name=safe_name)

    stored_files: list[tuple[str, object]] = []
    try:
        for upload_file in files:
            document_id = generate_uuid()
            stored = await store_uploaded_document_file(
                settings=settings,
                company_id=company.id,
                document_id=document_id,
                upload_file=upload_file,
            )
            stored_files.append((document_id, stored))
    except ExternalStorageError as exc:
        # Roll back any partial uploads, then surface a clean 502 instead of a 500.
        for _doc_id, stored in stored_files:
            try:
                await delete_stored_document_file(settings=settings, file_path=stored.file_path)
            except Exception:  # noqa: BLE001 — cleanup must not mask the original error
                pass
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Object storage upload failed: {exc}",
        ) from exc

    documents = []
    try:
        for document_id, stored in stored_files:
            doc = create_document_record(
                db_session,
                document_id=document_id,
                company_id=company.id,
                uploaded_by=user.id,
                stored_file=stored,
            )
            documents.append(doc)
        db_session.commit()
        background_tasks.add_task(
            run_embedding_pipeline_for_company,
            database_url=settings.database_url,
            upload_root=settings.upload_root,
            company_id=company.id,
        )
    except SQLAlchemyError as exc:
        db_session.rollback()
        for _doc_id, stored in stored_files:
            await delete_stored_document_file(settings=settings, file_path=stored.file_path)
        raise exc

    for doc in documents:
        db_session.refresh(doc)

    return [build_document_response(doc) for doc in documents]


@router.post(
    "/{company_id}/documents/uploads",
    response_model=DocumentUploadsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_company_document_uploads(
    company_id: str,
    payload: DocumentUploadsRequest,
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> DocumentUploadsResponse:
    """Mint per-file Supabase signed upload URLs so the browser can ``PUT`` directly.

    This endpoint never receives the file bytes. The client should:
      1. ``PUT`` each ticket's ``upload_url`` with the file body and the ticket's
         ``content_type`` header.
      2. Call :func:`post_company_document_confirm` to finalize the documents.

    When Supabase is not configured (e.g. local dev) the response signals
    ``mode="multipart"`` and the client must fall back to the legacy multipart
    POST endpoint.
    """
    identity = get_authenticated_user_identity(session_state)
    user, _created = upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    company = get_owned_company(db_session, company_id=company_id, owner_id=user.id)

    if not uses_supabase_storage(settings):
        return DocumentUploadsResponse(mode="multipart", uploads=[])

    safe_names: list[str] = []
    for item in payload.files:
        assert_pdf_metadata(
            file_name=item.file_name,
            content_type=item.content_type,
            file_size=item.file_size,
        )
        safe_names.append(sanitize_file_name(item.file_name))

    seen: set[str] = set()
    for safe_name in safe_names:
        if safe_name in seen:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate file name in batch: '{safe_name}'.",
            )
        seen.add(safe_name)
        ensure_document_name_is_available(db_session, company_id=company.id, file_name=safe_name)

    tickets: list[DocumentUploadTicket] = []
    try:
        for item, safe_name in zip(payload.files, safe_names, strict=True):
            document_id = generate_uuid()
            relative_path = build_storage_relative_path(
                company_id=company.id, document_id=document_id, safe_name=safe_name
            )
            upload_url = await create_supabase_signed_upload_url(
                settings=settings, file_path=relative_path
            )
            tickets.append(
                DocumentUploadTicket(
                    document_id=document_id,
                    file_name=safe_name,
                    file_path=relative_path,
                    upload_url=upload_url,
                    content_type=item.content_type,
                )
            )
    except ExternalStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not mint upload URL: {exc}",
        ) from exc

    return DocumentUploadsResponse(mode="direct", uploads=tickets)


@router.post(
    "/{company_id}/documents/confirm",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def post_company_document_confirm(
    company_id: str,
    payload: DocumentConfirmRequest,
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
    background_tasks: BackgroundTasks,
) -> list[DocumentResponse]:
    """Persist DB rows for files the browser has just PUT to Supabase directly.

    Verifies each object actually exists in the configured bucket (HEAD), reads
    the authoritative size from the ``Content-Length`` header, then inserts the
    metadata rows in a single transaction and triggers the embedding pipeline.
    """
    if not uses_supabase_storage(settings):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Direct-upload confirmation is only available when Supabase storage is configured.",
        )

    identity = get_authenticated_user_identity(session_state)
    user, _created = upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    company = get_owned_company(db_session, company_id=company_id, owner_id=user.id)

    expected_prefix = f"storage/{company.id}/"
    for item in payload.documents:
        if not item.file_path.startswith(expected_prefix):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"file_path {item.file_path!r} does not belong to this company.",
            )
        ensure_document_name_is_available(db_session, company_id=company.id, file_name=item.file_name)

    stored_files: list[tuple[str, StoredDocumentFile]] = []
    try:
        for item in payload.documents:
            object_size = await head_supabase_object(settings=settings, file_path=item.file_path)
            if object_size is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"No object found at {item.file_path!r}. "
                        "The browser upload may have failed; please retry."
                    ),
                )
            stored_files.append(
                (
                    item.document_id,
                    StoredDocumentFile(
                        file_name=item.file_name,
                        file_path=item.file_path,
                        file_size=object_size,
                        file_type=item.content_type,
                    ),
                )
            )
    except ExternalStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not verify uploaded objects: {exc}",
        ) from exc

    documents = []
    try:
        for document_id, stored in stored_files:
            doc = create_document_record(
                db_session,
                document_id=document_id,
                company_id=company.id,
                uploaded_by=user.id,
                stored_file=stored,
            )
            documents.append(doc)
        db_session.commit()
        background_tasks.add_task(
            run_embedding_pipeline_for_company,
            database_url=settings.database_url,
            upload_root=settings.upload_root,
            company_id=company.id,
        )
    except SQLAlchemyError as exc:
        db_session.rollback()
        for _doc_id, stored in stored_files:
            try:
                await delete_stored_document_file(settings=settings, file_path=stored.file_path)
            except Exception:  # noqa: BLE001 — cleanup must not mask the original error
                pass
        raise exc

    for doc in documents:
        db_session.refresh(doc)

    return [build_document_response(doc) for doc in documents]


@router.post(
    "/{company_id}/embed",
    response_model=EmbedTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_company_embed(
    company_id: str,
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
    background_tasks: BackgroundTasks,
) -> EmbedTriggerResponse:
    """Trigger background embedding for all pending documents of a company.

    Useful for retrying failed embeddings or processing documents uploaded before
    the embedding service was configured. The caller gets an immediate 202 response
    while the job runs asynchronously. Only the company owner may trigger this.
    """
    identity = get_authenticated_user_identity(session_state)
    user, _created = upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    company = get_owned_company(db_session, company_id=company_id, owner_id=user.id)

    pending = count_pending_documents(db_session, company_id=company.id, include_failed=True)
    background_tasks.add_task(
        run_embedding_pipeline_for_company,
        database_url=settings.database_url,
        upload_root=settings.upload_root,
        company_id=company.id,
        include_failed=True,
    )
    return EmbedTriggerResponse(
        message=f"Embedding started for {pending} pending document(s).",
        company_id=company.id,
    )
