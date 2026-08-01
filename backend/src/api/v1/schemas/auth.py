"""Request and response schemas for first-party authentication."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


class AuthUserResponse(BaseModel):
    """Authenticated user profile returned to the browser session layer."""

    id: str
    email: str | None
    name: str | None = None
    avatar_url: str | None = None
    created_at: datetime


class AuthResponse(BaseModel):
    """Session token and profile returned after a successful auth flow."""

    token: str
    expires_in: int
    user: AuthUserResponse


class ManualAuthRequest(BaseModel):
    """Email and password payload for manual registration or login."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=256)
    name: str | None = Field(default=None, max_length=120)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        """Trim optional display names and store blank values as null."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class GoogleCodeAuthRequest(BaseModel):
    """Authorization-code payload received from the frontend Google callback."""

    code: str = Field(..., min_length=1)
    redirect_uri: str = Field(..., min_length=1, max_length=512)
