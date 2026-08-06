"""Account creation, recovery, linking, and Google OAuth helpers."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
import hashlib
import secrets

import httpx
from fastapi import HTTPException, status
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.auth import (
    UserIdentity,
    create_session_token,
    generate_user_id,
    hash_password,
    normalize_email,
    verify_password,
)
from src.core.config import Settings
from src.models import PendingEmailVerification, User


@dataclass(frozen=True)
class GoogleProfile:
    """Verified Google profile fields used for local account linking."""

    google_sub: str
    email: str
    name: str | None
    avatar_url: str | None


def build_auth_response(settings: Settings, user: User) -> dict:
    """Build the token-bearing auth response for an authenticated local user."""
    token = create_session_token(
        settings=settings,
        identity=UserIdentity(user_id=user.id, email=user.email),
    )
    return {
        "token": token,
        "expires_in": settings.auth_session_expiry_seconds,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "avatar_url": user.avatar_url,
            "created_at": user.created_at,
        },
    }


def find_user_by_email(session: Session, email: str) -> User | None:
    """Return the oldest user row matching a normalized email address."""
    normalized = normalize_email(email)
    return (
        session.query(User)
        .filter(func.lower(User.email) == normalized)
        .order_by(User.created_at.asc())
        .first()
    )


def start_manual_registration(
    session: Session, *, email: str, password: str, name: str | None
) -> tuple[PendingEmailVerification, str]:
    """Store a pending password registration and return its one-time email token."""
    normalized = normalize_email(email)
    user = find_user_by_email(session, normalized)
    if user is not None and user.password_hash:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.")

    token = secrets.token_urlsafe(32)
    pending = session.query(PendingEmailVerification).filter(PendingEmailVerification.email == normalized).one_or_none()
    if pending is None:
        pending = PendingEmailVerification(
            email=normalized,
            password_hash=hash_password(password),
            name=name,
            token_hash=_hash_email_verification_token(token),
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        session.add(pending)
    else:
        pending.password_hash = hash_password(password)
        pending.name = name
        pending.token_hash = _hash_email_verification_token(token)
        pending.expires_at = datetime.now(UTC) + timedelta(minutes=30)
    session.flush()
    return pending, token


def confirm_email_verification(session: Session, *, token: str) -> User:
    """Create or complete a local account from a valid, single-use email link."""
    token_hash = _hash_email_verification_token(token)
    pending = (
        session.query(PendingEmailVerification)
        .filter(PendingEmailVerification.token_hash == token_hash)
        .with_for_update()
        .one_or_none()
    )
    now = datetime.now(UTC)
    if pending is None or pending.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This email confirmation link is invalid or has expired.",
        )

    user = find_user_by_email(session, pending.email)
    if user is None:
        user = User(
            id=generate_user_id(),
            email=pending.email,
            password_hash=pending.password_hash,
            name=pending.name,
        )
        session.add(user)
    elif user.password_hash:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.")
    else:
        user.password_hash = pending.password_hash
        if pending.name and not user.name:
            user.name = pending.name

    session.delete(pending)
    session.flush()
    return user


def authenticate_manual_user(session: Session, *, email: str, password: str) -> User:
    """Validate manual credentials and return the matching user."""
    user = find_user_by_email(session, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="We couldn't find an account with that email address.",
        )
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password. Please try again.")
    return user


def issue_password_reset_token(user: User) -> str:
    """Create a short-lived single-use reset token and store only its hash."""
    token = secrets.token_urlsafe(32)
    user.password_reset_token_hash = _hash_password_reset_token(token)
    user.password_reset_expires_at = datetime.now(UTC) + timedelta(minutes=30)
    return token


async def send_password_reset_email(
    *,
    sendgrid_api_key: str,
    sender_email: str,
    recipient_email: str,
    reset_url: str,
) -> None:
    """Deliver a password-reset link without exposing the token in application logs."""
    message = Mail(
        from_email=sender_email,
        to_emails=recipient_email,
        subject="Reset your Ubuntu Voice password",
        html_content=(
            "<p>We received a request to reset your Ubuntu Voice password.</p>"
            f'<p><a href="{escape(reset_url, quote=True)}">Reset your password</a></p>'
            "<p>This link expires in 30 minutes and can be used once. If you did not request this, you can ignore this email.</p>"
        ),
    )

    def send_message():
        return SendGridAPIClient(sendgrid_api_key).send(message)

    response = await asyncio.to_thread(send_message)
    if response.status_code >= 400:
        raise RuntimeError(f"SendGrid email delivery failed with status {response.status_code}.")


async def send_email_verification_email(
    *,
    sendgrid_api_key: str,
    sender_email: str,
    recipient_email: str,
    verification_url: str,
) -> None:
    """Deliver the one-time link that activates a manual registration."""
    message = Mail(
        from_email=sender_email,
        to_emails=recipient_email,
        subject="Confirm your Ubuntu Voice email",
        html_content=(
            "<p>Thanks for creating an Ubuntu Voice account.</p>"
            f'<p><a href="{escape(verification_url, quote=True)}">Confirm your email</a></p>'
            "<p>This link expires in 30 minutes. If you did not create this account, you can ignore this email.</p>"
        ),
    )

    def send_message():
        return SendGridAPIClient(sendgrid_api_key).send(message)

    response = await asyncio.to_thread(send_message)
    if response.status_code >= 400:
        raise RuntimeError(f"SendGrid email delivery failed with status {response.status_code}.")


def reset_password(session: Session, *, token: str, password: str) -> None:
    """Replace a password when presented with a valid, unexpired reset token."""
    token_hash = _hash_password_reset_token(token)
    user = session.query(User).filter(User.password_reset_token_hash == token_hash).with_for_update().one_or_none()
    now = datetime.now(UTC)
    if user is None or user.password_reset_expires_at is None or user.password_reset_expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This password reset link is invalid or has expired.")
    user.password_hash = hash_password(password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    session.flush()


def _hash_password_reset_token(token: str) -> str:
    """Create a non-reversible database value for a reset token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _hash_email_verification_token(token: str) -> str:
    """Create a non-reversible database value for an email-verification token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def upsert_google_user(session: Session, *, profile: GoogleProfile) -> User:
    """Create or link a user from a verified Google profile."""
    user = session.query(User).filter(User.google_sub == profile.google_sub).one_or_none()
    if user is None:
        user = find_user_by_email(session, profile.email)

    if user is None:
        user = User(
            id=generate_user_id(),
            email=profile.email,
            google_sub=profile.google_sub,
            name=profile.name,
            avatar_url=profile.avatar_url,
        )
        session.add(user)
    else:
        user.email = profile.email
        user.google_sub = profile.google_sub
        if profile.name:
            user.name = profile.name
        if profile.avatar_url:
            user.avatar_url = profile.avatar_url

    try:
        session.flush()
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This Google account is already linked to another user.",
        ) from exc
    return user


async def exchange_google_code_for_profile(
    *,
    settings: Settings,
    code: str,
    redirect_uri: str,
) -> GoogleProfile:
    """Exchange a Google authorization code and return a verified email profile."""
    if not settings.google_client_id or not settings.google_client_secrete:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Google sign-in is not configured.")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secrete,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            if token_response.status_code != 200:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google authorization failed.")
            access_token = token_response.json().get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google authorization failed.")

            userinfo_response = await client.get(
                "https://openidconnect.googleapis.com/v1/userinfo",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Google authorization is unavailable.") from exc
        if userinfo_response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google profile lookup failed.")

    raw_profile = userinfo_response.json()
    google_sub = raw_profile.get("sub")
    email = raw_profile.get("email")
    email_verified = raw_profile.get("email_verified")
    if not isinstance(google_sub, str) or not google_sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google profile is missing an id.")
    if not isinstance(email, str) or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google profile is missing an email.")
    if email_verified is not True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Google email is not verified.")

    name = raw_profile.get("name")
    picture = raw_profile.get("picture")
    return GoogleProfile(
        google_sub=google_sub,
        email=normalize_email(email),
        name=name if isinstance(name, str) and name.strip() else None,
        avatar_url=picture if isinstance(picture, str) and picture.strip() else None,
    )
