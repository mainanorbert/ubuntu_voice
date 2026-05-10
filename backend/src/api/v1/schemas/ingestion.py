"""Request and response models for tenant setup and document ingestion."""

from datetime import datetime
import re
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


def normalize_phone_number(value: str) -> str:
    """Normalize a readable phone number and reject invalid lengths."""
    stripped = value.strip()
    compact = re.sub(r"[\s().-]", "", stripped)
    if compact.startswith("00"):
        compact = f"+{compact[2:]}"
    if not re.fullmatch(r"\+?[1-9]\d{6,14}", compact):
        raise ValueError("Phone must be a valid international number with 7 to 15 digits.")
    return compact


class RegisteredUserResponse(BaseModel):
    """Response payload after syncing the authenticated Clerk user locally."""

    id: str = Field(..., examples=["user_2zExample123"])
    email: str | None = Field(default=None, examples=["owner@example.com"])
    created: bool = Field(..., examples=[True])
    created_at: datetime


class CompanyCreateRequest(BaseModel):
    """Payload for creating a new tenant company."""

    name: str = Field(..., min_length=1, examples=["Acme Support"])
    email: EmailStr = Field(..., examples=["support@acme.example"])
    phone: str | None = Field(default=None, min_length=7, max_length=20, examples=["+254712345678"])
    description: str | None = Field(
        default=None,
        max_length=300,
        examples=["Answers questions about local peacebuilding services and referral documents."],
    )

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        """Normalize and validate agent phone numbers when provided."""
        if value is None or not value.strip():
            return None
        return normalize_phone_number(value)

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        """Store blank descriptions as null after trimming whitespace."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class CompanyResponse(BaseModel):
    """Serialized company returned to API clients."""

    id: str
    name: str
    email: str
    phone: str | None
    description: str | None
    owner_id: str
    created_at: datetime


class DocumentResponse(BaseModel):
    """Serialized document metadata returned by ingestion endpoints."""

    id: str
    company_id: str
    uploaded_by: str
    file_name: str
    file_path: str
    file_size: int | None
    file_type: str | None
    status: str
    is_embedded: bool
    created_at: datetime


class CompanyWithDocumentsResponse(BaseModel):
    """Convenience response containing a company and its current documents."""

    company: CompanyResponse
    documents: list[DocumentResponse]


class EmbedTriggerResponse(BaseModel):
    """Response returned when an embedding job is dispatched to the background."""

    message: str = Field(..., examples=["Embedding started for 3 pending document(s)."])
    company_id: str = Field(..., examples=["a1b2c3d4-..."])


class DocumentUploadRequestItem(BaseModel):
    """Per-file metadata sent by the client when requesting upload tickets."""

    file_name: str = Field(..., min_length=1, max_length=512)
    file_size: int = Field(..., ge=1)
    content_type: str = Field(default="application/pdf", min_length=1, max_length=128)


class DocumentUploadsRequest(BaseModel):
    """Body for the signed-upload mint endpoint."""

    files: list[DocumentUploadRequestItem] = Field(..., min_length=1, max_length=20)


class DocumentUploadTicket(BaseModel):
    """One file's worth of pre-signed upload instructions."""

    document_id: str
    file_name: str
    file_path: str
    upload_url: str
    method: Literal["PUT"] = "PUT"
    content_type: str


class DocumentUploadsResponse(BaseModel):
    """Mint-endpoint response. ``mode == 'multipart'`` tells the client to fall back."""

    mode: Literal["direct", "multipart"]
    uploads: list[DocumentUploadTicket] = Field(default_factory=list)


class DocumentConfirmItem(BaseModel):
    """Per-file metadata sent after a direct upload completed in the browser."""

    document_id: str
    file_path: str
    file_name: str
    content_type: str = Field(default="application/pdf")


class DocumentConfirmRequest(BaseModel):
    """Body for the confirm endpoint that finalizes direct uploads in the database."""

    documents: list[DocumentConfirmItem] = Field(..., min_length=1, max_length=20)
