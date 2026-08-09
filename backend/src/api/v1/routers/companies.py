"""Routes for company management and multi-file document ingestion."""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.api.v1.schemas.ingestion import (
    CompanyCreateRequest,
    AgentApprovalRequest,
    CompanyResponse,
    CompanyUpdateRequest,
    CompanyWithDocumentsResponse,
    DocumentConfirmRequest,
    DocumentResponse,
    DocumentUploadsRequest,
    DocumentUploadsResponse,
    DocumentUploadTicket,
    EmbedTriggerResponse,
)
from src.core.auth import UserIdentity, get_authenticated_user_identity, require_admin, require_auth_session
from src.core.config import Settings
from src.core.dependencies import get_db_session, get_settings
from src.models import (
    Company,
    Document,
    DocumentChunk,
    EvaluationQuestion,
    EvaluationResult,
    EvaluationRun,
    GuardrailEvent,
    IncidentStatistic,
    WhatsAppAgentSession,
    generate_uuid,
)
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
    update_owned_company,
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
        description=company.description,
        owner_id=company.owner_id,
        is_approved=company.is_approved,
        approval_status=company.approval_status,
        approved_by=company.approved_by,
        approved_at=company.approved_at,
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
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> list[CompanyResponse]:
    """List companies owned by the authenticated user."""
    identity = get_authenticated_user_identity(session_state)
    companies = list_companies_for_owner(db_session, owner_id=identity.user_id)
    return [build_company_response(c) for c in companies]


@router.get("/public", response_model=list[CompanyResponse])
async def get_public_companies(
    db_session: Annotated[Session, Depends(get_db_session)],
) -> list[CompanyResponse]:
    """List available agents for the public chat and agent directory."""
    companies = db_session.query(Company).filter(Company.is_approved.is_(True)).order_by(Company.created_at.desc()).all()
    return [build_company_response(c) for c in companies]


@router.get("/admin", response_model=list[CompanyResponse])
async def get_admin_companies(
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> list[CompanyResponse]:
    """List every agent for configured administrators only."""
    identity = get_authenticated_user_identity(session_state)
    require_admin(identity, settings)
    companies = db_session.query(Company).order_by(Company.created_at.desc()).all()
    return [build_company_response(c) for c in companies]


@router.patch("/{company_id}/approval", response_model=CompanyResponse)
async def patch_agent_approval(
    company_id: str,
    body: AgentApprovalRequest,
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> CompanyResponse:
    """Approve or suspend an agent, restricted to ADMIN_EMAILS."""
    identity = get_authenticated_user_identity(session_state)
    require_admin(identity, settings)
    company = db_session.get(Company, company_id)
    if company is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found.")
    company.is_approved = body.approved
    company.approval_status = "approved" if body.approved else "suspended"
    company.approved_by = identity.email if body.approved else None
    company.approved_at = datetime.now(timezone.utc) if body.approved else None
    db_session.commit()
    db_session.refresh(company)
    return build_company_response(company)


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def post_company(
    body: CompanyCreateRequest,
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> CompanyResponse:
    """Create an agent for the authenticated user using a unique contact email."""
    identity = get_authenticated_user_identity(session_state)
    user, _created = upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    company, _new = get_or_create_company(
        db_session,
        owner_id=user.id,
        name=body.name,
        email=str(body.email),
        phone=body.phone,
        description=body.description,
    )
    db_session.commit()
    db_session.refresh(company)
    return build_company_response(company)


@router.patch("/{company_id}", response_model=CompanyResponse)
async def patch_company(
    company_id: str,
    body: CompanyUpdateRequest,
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> CompanyResponse:
    """Update editable profile fields for an authenticated owner's agent."""
    identity = get_authenticated_user_identity(session_state)
    company = update_owned_company(
        db_session,
        company_id=company_id,
        owner_id=identity.user_id,
        fields_to_update=body.model_fields_set,
        name=body.name,
        email=str(body.email) if body.email is not None else None,
        phone=body.phone,
        description=body.description,
    )
    db_session.commit()
    db_session.refresh(company)
    return build_company_response(company)


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company(
    company_id: str,
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> None:
    """Permanently delete an owned agent and all associated data."""
    identity = get_authenticated_user_identity(session_state)
    company = get_owned_company(db_session, company_id=company_id, owner_id=identity.user_id)
    documents = list_documents(db_session, company_id=company.id)

    try:
        # Remove external files first. Missing objects are safe to retry; if a
        # storage request fails, keep the database records so deletion can be retried.
        for document in documents:
            await delete_stored_document_file(settings=settings, file_path=document.file_path)
    except ExternalStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The agent files could not be removed from storage. Please try again.",
        ) from exc

    try:
        run_ids = [
            run_id
            for (run_id,) in db_session.query(EvaluationRun.id)
            .filter(EvaluationRun.company_id == company.id)
            .all()
        ]
        if run_ids:
            db_session.query(EvaluationResult).filter(EvaluationResult.run_id.in_(run_ids)).delete(
                synchronize_session=False
            )
        db_session.query(EvaluationRun).filter(EvaluationRun.company_id == company.id).delete(
            synchronize_session=False
        )
        db_session.query(EvaluationQuestion).filter(EvaluationQuestion.company_id == company.id).delete(
            synchronize_session=False
        )
        db_session.query(IncidentStatistic).filter(IncidentStatistic.company_id == company.id).delete(
            synchronize_session=False
        )
        db_session.query(GuardrailEvent).filter(GuardrailEvent.company_id == company.id).delete(
            synchronize_session=False
        )
        db_session.query(WhatsAppAgentSession).filter(WhatsAppAgentSession.company_id == company.id).delete(
            synchronize_session=False
        )
        db_session.query(DocumentChunk).filter(DocumentChunk.company_id == company.id).delete(
            synchronize_session=False
        )
        db_session.query(Document).filter(Document.company_id == company.id).delete(
            synchronize_session=False
        )
        db_session.delete(company)
        db_session.commit()
    except SQLAlchemyError as exc:
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The agent could not be deleted. Please try again.",
        ) from exc


@router.get("/{company_id}/documents", response_model=CompanyWithDocumentsResponse)
async def get_company_documents(
    company_id: str,
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
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


@router.delete("/{company_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_document(
    company_id: str,
    document_id: str,
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> None:
    """Permanently delete an owned document, its stored file, and its embeddings."""
    identity = get_authenticated_user_identity(session_state)
    user, _created = upsert_user(db_session, user_id=identity.user_id, email=identity.email)
    company = get_owned_company(db_session, company_id=company_id, owner_id=user.id)
    document = (
        db_session.query(Document)
        .filter(Document.id == document_id, Document.company_id == company.id)
        .one_or_none()
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    try:
        # Do not remove the database record unless durable storage has accepted the deletion.
        # A missing object is treated as deleted by the storage adapter, making retries safe.
        await delete_stored_document_file(settings=settings, file_path=document.file_path)
    except ExternalStorageError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The document could not be removed from storage. Please try again.",
        ) from exc

    try:
        # Explicit removal protects existing deployments even if an older database
        # migration lacks the document_chunks foreign-key cascade.
        db_session.query(DocumentChunk).filter(DocumentChunk.document_id == document.id).delete(
            synchronize_session=False
        )
        db_session.delete(document)
        db_session.commit()
    except SQLAlchemyError as exc:
        db_session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The document could not be deleted. Please try again.",
        ) from exc


@router.post(
    "/{company_id}/documents",
    response_model=list[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def post_company_documents(
    company_id: str,
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
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
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
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
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
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
    session_state: Annotated[UserIdentity, Depends(require_auth_session)],
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
