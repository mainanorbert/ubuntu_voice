"""Routes for manual and Google authentication."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.v1.schemas.auth import AuthResponse, AuthUserResponse, GoogleCodeAuthRequest, ManualAuthRequest
from src.core.auth import UserIdentity, require_auth_session
from src.core.config import Settings
from src.core.dependencies import get_db_session, get_settings
from src.services.auth import (
    authenticate_manual_user,
    build_auth_response,
    exchange_google_code_for_profile,
    register_manual_user,
    upsert_google_user,
)
from src.services.cost_monitoring import ensure_user_spend_row
from src.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


def build_user_response(user: User) -> AuthUserResponse:
    """Serialize a local user row for account UI."""
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def post_auth_register(
    body: ManualAuthRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> AuthResponse:
    """Register a manual email/password user and issue a first-party session."""
    user = register_manual_user(
        db_session,
        email=str(body.email),
        password=body.password,
        name=body.name,
    )
    ensure_user_spend_row(db_session, user_id=user.id, email=user.email)
    db_session.commit()
    db_session.refresh(user)
    return AuthResponse.model_validate(build_auth_response(settings, user))


@router.post("/login", response_model=AuthResponse)
async def post_auth_login(
    body: ManualAuthRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> AuthResponse:
    """Authenticate an email/password user and issue a first-party session."""
    user = authenticate_manual_user(db_session, email=str(body.email), password=body.password)
    ensure_user_spend_row(db_session, user_id=user.id, email=user.email)
    db_session.commit()
    db_session.refresh(user)
    return AuthResponse.model_validate(build_auth_response(settings, user))


@router.post("/google", response_model=AuthResponse)
async def post_auth_google(
    body: GoogleCodeAuthRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> AuthResponse:
    """Exchange a Google OAuth code, link by email when possible, and issue a session."""
    profile = await exchange_google_code_for_profile(
        settings=settings,
        code=body.code,
        redirect_uri=body.redirect_uri,
    )
    user = upsert_google_user(db_session, profile=profile)
    ensure_user_spend_row(db_session, user_id=user.id, email=user.email)
    db_session.commit()
    db_session.refresh(user)
    return AuthResponse.model_validate(build_auth_response(settings, user))


@router.get("/me", response_model=AuthUserResponse)
async def get_auth_me(
    identity: Annotated[UserIdentity, Depends(require_auth_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> AuthUserResponse:
    """Return the local profile for the authenticated session."""
    user = db_session.get(User, identity.user_id)
    if user is None:
        user = User(id=identity.user_id, email=identity.email)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return build_user_response(user)
