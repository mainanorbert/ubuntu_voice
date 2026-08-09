"""First-party bearer session authentication for FastAPI routes."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from src.core.config import Settings
from src.core.dependencies import get_settings


@dataclass(frozen=True)
class UserIdentity:
    """Authenticated user fields extracted from a verified first-party session."""

    user_id: str
    email: str | None


def get_authenticated_user_identity(state: UserIdentity) -> UserIdentity:
    """Return the already-verified authenticated user identity."""
    return state


def normalize_email(email: str) -> str:
    """Normalize an email address for account matching."""
    return email.strip().lower()


def is_admin_email(email: str | None, admin_emails: str) -> bool:
    """Return whether an email is explicitly listed in ADMIN_EMAILS."""
    if not email:
        return False
    return normalize_email(email) in {
        normalize_email(value) for value in admin_emails.split(",") if value.strip()
    }


def require_admin(identity: UserIdentity, settings: Settings) -> None:
    """Reject authenticated users whose email is not configured as an administrator."""
    if not is_admin_email(identity.email, settings.admin_emails):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrator access is required.")


def generate_user_id() -> str:
    """Return a local text user ID compatible with existing foreign keys."""
    return f"user_{secrets.token_urlsafe(18)}"


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a per-user random salt."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 210_000)
    return f"pbkdf2_sha256$210000${_b64url_encode(salt)}${_b64url_encode(digest)}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    """Verify a password against a stored PBKDF2 hash."""
    if not stored_hash:
        return False
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = _b64url_decode(salt_raw)
        expected = _b64url_decode(digest_raw)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_session_token(*, settings: Settings, identity: UserIdentity) -> str:
    """Create a signed bearer session token for an authenticated user."""
    now = int(time.time())
    payload = {
        "sub": identity.user_id,
        "email": identity.email,
        "iat": now,
        "exp": now + settings.auth_session_expiry_seconds,
    }
    encoded_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(encoded_payload, settings.auth_session_secret)
    return f"{encoded_payload}.{signature}"


def verify_session_token(*, settings: Settings, token: str) -> UserIdentity:
    """Validate a signed bearer session token and return its user identity."""
    try:
        encoded_payload, signature = token.split(".", 1)
    except ValueError as exc:
        raise _unauthorized("Invalid session token.") from exc

    expected_signature = _sign(encoded_payload, settings.auth_session_secret)
    if not hmac.compare_digest(signature, expected_signature):
        raise _unauthorized("Invalid session token.")

    try:
        payload = json.loads(_b64url_decode(encoded_payload))
    except (json.JSONDecodeError, ValueError) as exc:
        raise _unauthorized("Invalid session token.") from exc

    user_id = payload.get("sub")
    expires_at = payload.get("exp")
    email = payload.get("email")
    if not isinstance(user_id, str) or not user_id:
        raise _unauthorized("Invalid session token.")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        raise _unauthorized("Session expired.")
    if email is not None and not isinstance(email, str):
        raise _unauthorized("Invalid session token.")
    return UserIdentity(user_id=user_id, email=email)


async def require_auth_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserIdentity:
    """Reject requests unless a valid first-party bearer token is present."""
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized("Unauthorized.")
    return verify_session_token(settings=settings, token=token)


async def get_optional_auth_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserIdentity | None:
    """Return a verified session when present, allowing public read-only flows."""
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return verify_session_token(settings=settings, token=token)


def _sign(value: str, secret: str) -> str:
    """Sign a string with HMAC-SHA256."""
    digest = hmac.new(secret.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def _b64url_encode(value: bytes) -> str:
    """Encode bytes as unpadded base64url text."""
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    """Decode unpadded base64url text."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _unauthorized(detail: str) -> HTTPException:
    """Build a consistent 401 response for auth failures."""
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)
