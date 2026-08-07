"""Routes for manual and Google authentication."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from src.api.v1.schemas.auth import (
    AuthResponse,
    AuthUserResponse,
    EmailVerificationConfirmRequest,
    GoogleCodeAuthRequest,
    ManualAuthRequest,
    ManualRegistrationRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegistrationPendingResponse,
)
from src.core.auth import UserIdentity, is_admin_email, require_auth_session
from src.core.config import Settings
from src.core.dependencies import get_db_session, get_settings
from src.services.auth import (
    authenticate_manual_user,
    build_auth_response,
    confirm_email_verification,
    exchange_google_code_for_profile,
    find_user_by_email,
    start_manual_registration,
    issue_password_reset_token,
    reset_password,
    send_password_reset_email,
    send_email_verification_email,
    upsert_google_user,
)
from src.services.cost_monitoring import ensure_user_spend_row
from src.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

PASSWORD_RESET_MESSAGE = "If an account with that email can use password sign-in, we sent a reset link."
EMAIL_VERIFICATION_MESSAGE = "Check your inbox to confirm your email and finish creating your account."


def build_user_response(user: User, settings: Settings | None = None) -> AuthUserResponse:
    """Serialize a local user row for account UI."""
    return AuthUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
        created_at=user.created_at,
        is_admin=is_admin_email(user.email, settings.admin_emails) if settings is not None else False,
    )


@router.post("/register", response_model=RegistrationPendingResponse, status_code=status.HTTP_202_ACCEPTED)
async def post_auth_register(
    body: ManualRegistrationRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> RegistrationPendingResponse:
    """Start manual registration and send an email link before creating an account."""
    if not settings.sendgrid_api_key or not settings.sendgrid_from_email:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Email confirmation is not available right now. Please try again later.")
    pending, token = start_manual_registration(
        db_session,
        email=str(body.email),
        password=body.password,
        name=body.name,
    )
    verification_url = f"{settings.frontend_base_url.rstrip('/')}/confirm-email?token={token}"
    try:
        await send_email_verification_email(
            sendgrid_api_key=settings.sendgrid_api_key,
            sender_email=settings.sendgrid_from_email,
            recipient_email=pending.email,
            verification_url=verification_url,
        )
    except RuntimeError:
        db_session.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="We couldn't send the confirmation email. Please try again.")
    db_session.commit()
    return RegistrationPendingResponse(message=EMAIL_VERIFICATION_MESSAGE)


@router.post("/email-verification/confirm", response_model=AuthResponse)
async def post_email_verification_confirm(
    body: EmailVerificationConfirmRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> AuthResponse:
    """Activate a manual account after its email owner confirms the link."""
    user = confirm_email_verification(db_session, token=body.token)
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


@router.post("/password-reset/request")
async def post_password_reset_request(
    body: PasswordResetRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, str]:
    """Send an expiring reset link without revealing whether an account exists."""
    user = find_user_by_email(db_session, str(body.email))
    if user is None or not user.password_hash:
        return {"message": PASSWORD_RESET_MESSAGE}
    if not settings.sendgrid_api_key or not settings.sendgrid_from_email:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Password reset email delivery is not configured.")

    token = issue_password_reset_token(user)
    reset_url = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={token}"
    try:
        await send_password_reset_email(
            sendgrid_api_key=settings.sendgrid_api_key,
            sender_email=settings.sendgrid_from_email,
            recipient_email=user.email or str(body.email),
            reset_url=reset_url,
        )
    except RuntimeError:
        db_session.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not send the password reset email. Please try again.")
    db_session.commit()
    return {"message": PASSWORD_RESET_MESSAGE}


@router.post("/password-reset/confirm")
async def post_password_reset_confirm(
    body: PasswordResetConfirmRequest,
    db_session: Annotated[Session, Depends(get_db_session)],
) -> dict[str, str]:
    """Accept a single-use reset link and save the new password."""
    reset_password(db_session, token=body.token, password=body.password)
    db_session.commit()
    return {"message": "Your password has been reset. You can now sign in."}


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
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> AuthUserResponse:
    """Return the local profile for the authenticated session."""
    user = db_session.get(User, identity.user_id)
    if user is None:
        user = User(id=identity.user_id, email=identity.email)
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return build_user_response(user, settings)
