"""Request and response schemas for first-party authentication."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_strong_password(value: str) -> str:
    """Require a password that is resilient to simple guessing attacks."""
    if len(value) < 12 or not any(character.islower() for character in value) or not any(
        character.isupper() for character in value
    ) or not any(character.isdigit() for character in value) or not any(not character.isalnum() for character in value):
        raise ValueError("Password must be at least 12 characters and include uppercase, lowercase, a number, and a symbol.")
    return value


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


class RegistrationPendingResponse(BaseModel):
    """Confirmation shown after a manual registration email is sent."""

    message: str


class EmailVerificationConfirmRequest(BaseModel):
    """One-time token from a manual-registration confirmation email."""

    token: str = Field(..., min_length=32, max_length=512)


class ManualAuthRequest(BaseModel):
    """Email and password payload for manual sign-in."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=256)


class ManualRegistrationRequest(ManualAuthRequest):
    """Validated identity and credentials required for manual registration."""

    first_name: str = Field(..., min_length=1, max_length=60)
    last_name: str = Field(..., min_length=1, max_length=60)

    @field_validator("first_name", "last_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        """Trim required name fields and reject whitespace-only values."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("This field is required.")
        return stripped

    @field_validator("password")
    @classmethod
    def require_strong_password(cls, value: str) -> str:
        return validate_strong_password(value)

    @property
    def name(self) -> str:
        """Provide the existing display-name storage format."""
        return f"{self.first_name} {self.last_name}"


class PasswordResetRequest(BaseModel):
    """Email address used to request a password-reset link."""

    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """Single-use reset token and replacement password."""

    token: str = Field(..., min_length=32, max_length=512)
    password: str = Field(..., min_length=12, max_length=256)

    @field_validator("password")
    @classmethod
    def require_strong_password(cls, value: str) -> str:
        return validate_strong_password(value)


class GoogleCodeAuthRequest(BaseModel):
    """Authorization-code payload received from the frontend Google callback."""

    code: str = Field(..., min_length=1)
    redirect_uri: str = Field(..., min_length=1, max_length=512)
