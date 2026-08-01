"""Account creation, linking, and Google OAuth helpers."""

from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status
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
from src.models import User


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


def register_manual_user(session: Session, *, email: str, password: str, name: str | None) -> User:
    """Create a password user, or add a password to an existing Google/email-matched user."""
    normalized = normalize_email(email)
    user = find_user_by_email(session, normalized)
    if user is not None:
        if user.password_hash:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already registered.")
        user.password_hash = hash_password(password)
        if name and not user.name:
            user.name = name
        session.flush()
        return user

    user = User(id=generate_user_id(), email=normalized, password_hash=hash_password(password), name=name)
    session.add(user)
    session.flush()
    return user


def authenticate_manual_user(session: Session, *, email: str, password: str) -> User:
    """Validate manual credentials and return the matching user."""
    user = find_user_by_email(session, email)
    if user is None or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    return user


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
