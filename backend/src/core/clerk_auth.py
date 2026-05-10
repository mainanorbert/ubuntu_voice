"""Clerk session verification for FastAPI routes."""

from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from clerk_backend_api import Clerk
from clerk_backend_api.security.types import AuthenticateRequestOptions, RequestState
from fastapi import Depends, HTTPException, Request

from src.core.config import Settings
from src.core.dependencies import get_settings


@dataclass(frozen=True)
class UserIdentity:
    """Extracted identity fields from a verified Clerk session token."""

    user_id: str
    email: str | None


def get_authenticated_user_identity(state: RequestState) -> UserIdentity:
    """Extract the Clerk user ID and email from a verified session state.

    Raises HTTP 401 if the sub claim is absent, which should not happen for
    a state that already passed ``require_clerk_session``.
    """
    payload: dict = state.payload or {}
    user_id: str = payload.get("sub", "")
    if not user_id:
        raise HTTPException(status_code=401, detail="Could not extract user identity from session token.")
    email: str | None = payload.get("email")
    return UserIdentity(user_id=user_id, email=email)


def parse_authorized_parties(raw: str) -> list[str]:
    """Split a comma-separated list of allowed frontend origins for Clerk JWTs."""
    return [part.strip() for part in raw.split(",") if part.strip()]


@lru_cache
def get_clerk_sdk(secret_key: str) -> Clerk:
    """Return a Clerk SDK client configured with the instance secret key."""
    return Clerk(bearer_auth=secret_key)


def build_authenticate_request_options(settings: Settings) -> AuthenticateRequestOptions:
    """Build Clerk ``AuthenticateRequestOptions`` from application settings."""
    parties = parse_authorized_parties(settings.clerk_authorized_parties)
    return AuthenticateRequestOptions(authorized_parties=parties)


async def require_clerk_session(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> RequestState:
    """Reject unauthenticated requests unless a valid Clerk session JWT is present."""
    sdk = get_clerk_sdk(settings.clerk_secret_key)
    options = build_authenticate_request_options(settings)
    state = await sdk.authenticate_request_async(request, options)
    if not state.is_signed_in:
        detail = state.message or "Unauthorized"
        raise HTTPException(status_code=401, detail=detail)
    return state
