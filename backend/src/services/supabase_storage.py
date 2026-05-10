"""Helpers for storing and retrieving document bytes in Supabase Storage."""

from __future__ import annotations

from urllib.parse import quote

import httpx

from src.core.config import Settings


# Per-phase HTTP budget for Supabase Storage requests.
# Uploads can be several MB on slow uplinks, so the write window is generous;
# connect/read remain short so dead hosts fail fast.
_SUPABASE_TIMEOUT = httpx.Timeout(connect=15.0, read=60.0, write=120.0, pool=15.0)


class ExternalStorageError(RuntimeError):
    """Raised when the external object storage service cannot complete a request."""


def describe_supabase_http_error(*, operation: str, exc: httpx.HTTPError) -> str:
    """Return a safe, actionable Supabase network error without exposing configured secrets."""
    if isinstance(exc, httpx.ConnectError):
        return (
            f"Supabase {operation} network error: could not reach the configured storage endpoint. "
            "Check SUPABASE_URL is your Supabase Project URL and that DNS/network access is available."
        )
    return f"Supabase {operation} network error: {type(exc).__name__}: {exc}"


def uses_supabase_storage(settings: Settings) -> bool:
    """Return True when the current settings fully configure Supabase Storage."""
    return bool(settings.supabase_url and settings.supabase_service_key)


def normalize_storage_file_path(file_path: str) -> str:
    """Validate and normalize a DB ``file_path`` into a storage object key."""
    prefix = "storage/"
    if not file_path.startswith(prefix):
        msg = f"Unexpected file_path format (expected '{prefix}' prefix): {file_path!r}"
        raise ValueError(msg)
    return file_path.lstrip("/")


def build_storage_object_url(*, settings: Settings, file_path: str) -> str:
    """Return the REST endpoint URL for a Supabase Storage object."""
    if not settings.supabase_url or not settings.supabase_service_key:
        raise ExternalStorageError("Supabase storage is not configured.")
    normalized_path = normalize_storage_file_path(file_path)
    encoded_path = quote(normalized_path, safe="/")
    return f"{settings.supabase_url}/storage/v1/object/{settings.supabase_bucket}/{encoded_path}"


def build_storage_headers(*, settings: Settings, content_type: str | None = None) -> dict[str, str]:
    """Build the server-side authorization headers for Supabase Storage requests."""
    if not settings.supabase_service_key:
        raise ExternalStorageError("Supabase service key is not configured.")
    headers = {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


async def upload_file_bytes_to_supabase(
    *,
    settings: Settings,
    file_path: str,
    file_bytes: bytes,
    content_type: str | None,
) -> None:
    """Upload the provided file bytes into the configured Supabase bucket."""
    url = build_storage_object_url(settings=settings, file_path=file_path)
    headers = build_storage_headers(settings=settings, content_type=content_type or "application/octet-stream")
    try:
        async with httpx.AsyncClient(timeout=_SUPABASE_TIMEOUT) as client:
            response = await client.post(url, headers=headers, content=file_bytes)
    except httpx.HTTPError as exc:
        raise ExternalStorageError(describe_supabase_http_error(operation="upload", exc=exc)) from exc
    if response.status_code not in {200, 201}:
        raise ExternalStorageError(
            f"Supabase upload failed with status {response.status_code}: {response.text[:300]}"
        )


def download_file_bytes_from_supabase(*, settings: Settings, file_path: str) -> bytes:
    """Download the full object contents for a previously stored document."""
    url = build_storage_object_url(settings=settings, file_path=file_path)
    headers = build_storage_headers(settings=settings)
    try:
        with httpx.Client(timeout=_SUPABASE_TIMEOUT) as client:
            response = client.get(url, headers=headers)
    except httpx.HTTPError as exc:
        raise ExternalStorageError(describe_supabase_http_error(operation="download", exc=exc)) from exc
    if response.status_code == 404:
        raise FileNotFoundError(f"Supabase object not found for file_path={file_path!r}")
    if response.status_code != 200:
        raise ExternalStorageError(
            f"Supabase download failed with status {response.status_code}: {response.text[:300]}"
        )
    return response.content


async def create_supabase_signed_upload_url(
    *,
    settings: Settings,
    file_path: str,
) -> str:
    """Mint a one-shot upload URL the browser can ``PUT`` bytes to directly.

    Returns the fully-qualified URL including the signed token. Supabase tokens
    expire after a short window (a few minutes), so callers should treat the
    URL as ephemeral.
    """
    if not settings.supabase_url or not settings.supabase_service_key:
        raise ExternalStorageError("Supabase storage is not configured.")
    normalized_path = normalize_storage_file_path(file_path)
    encoded_path = quote(normalized_path, safe="/")
    sign_url = (
        f"{settings.supabase_url}/storage/v1/object/upload/sign/"
        f"{settings.supabase_bucket}/{encoded_path}"
    )
    headers = {
        "apikey": settings.supabase_service_key,
        "Authorization": f"Bearer {settings.supabase_service_key}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=_SUPABASE_TIMEOUT) as client:
            response = await client.post(sign_url, headers=headers, json={})
    except httpx.HTTPError as exc:
        raise ExternalStorageError(describe_supabase_http_error(operation="signed-URL request", exc=exc)) from exc
    if response.status_code not in {200, 201}:
        raise ExternalStorageError(
            f"Supabase signed-URL request rejected with status {response.status_code}: {response.text[:300]}"
        )
    body = response.json()
    relative = body.get("url") if isinstance(body, dict) else None
    if not isinstance(relative, str) or not relative:
        raise ExternalStorageError(f"Supabase signed-URL response missing 'url' field: {body!r}")
    # Supabase returns a path like '/object/upload/sign/{bucket}/{path}?token=...'
    return f"{settings.supabase_url}/storage/v1{relative}"


async def head_supabase_object(*, settings: Settings, file_path: str) -> int | None:
    """Return the byte length of a stored object, or ``None`` if it does not exist."""
    url = build_storage_object_url(settings=settings, file_path=file_path)
    headers = build_storage_headers(settings=settings)
    try:
        async with httpx.AsyncClient(timeout=_SUPABASE_TIMEOUT) as client:
            response = await client.head(url, headers=headers)
    except httpx.HTTPError as exc:
        raise ExternalStorageError(describe_supabase_http_error(operation="HEAD", exc=exc)) from exc
    if response.status_code == 404:
        return None
    if response.status_code not in {200, 204}:
        raise ExternalStorageError(
            f"Supabase HEAD failed with status {response.status_code}: {response.text[:300]}"
        )
    length = response.headers.get("content-length")
    try:
        return int(length) if length is not None else None
    except ValueError:
        return None


async def delete_file_from_supabase(*, settings: Settings, file_path: str) -> None:
    """Delete a stored object from Supabase, ignoring objects that are already missing."""
    url = build_storage_object_url(settings=settings, file_path=file_path)
    headers = build_storage_headers(settings=settings)
    try:
        async with httpx.AsyncClient(timeout=_SUPABASE_TIMEOUT) as client:
            response = await client.delete(url, headers=headers)
    except httpx.HTTPError as exc:
        raise ExternalStorageError(describe_supabase_http_error(operation="delete", exc=exc)) from exc
    if response.status_code in {200, 202, 204, 404}:
        return
    raise ExternalStorageError(f"Supabase delete failed with status {response.status_code}: {response.text[:300]}")
