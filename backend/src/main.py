"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from src.api.v1.routers import agents, auth, companies, evaluations, monitoring, users, webhooks
from src.core.config import Settings
from src.core.database import Base
from src.core.dependencies import get_database_engine, get_settings
from src.core.pgvector_setup import database_url_is_postgresql, ensure_pgvector_extension
from src.core.rate_limit import SlidingWindowRateLimiter
import src.models  # noqa: F401
from src.services.supabase_storage import uses_supabase_storage


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Ensure required storage resources and database tables are ready."""
    settings: Settings = get_settings()
    if not uses_supabase_storage(settings):
        Path(settings.upload_root).expanduser().resolve().mkdir(parents=True, exist_ok=True)
    engine = get_database_engine(settings.database_url)
    if database_url_is_postgresql(settings.database_url):
        ensure_pgvector_extension(engine)
    Base.metadata.create_all(bind=engine)
    yield


def parse_csv_non_empty(raw: str) -> list[str]:
    """Split a comma-separated string into non-empty stripped parts."""
    return [part.strip() for part in raw.split(",") if part.strip()]


def maybe_install_cors_middleware(*, app: FastAPI, settings: Settings) -> None:
    """Install CORS middleware when configured origins are present."""
    allow_origins = parse_csv_non_empty(settings.cors_allowed_origins)
    if not allow_origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )


settings = get_settings()
is_production = settings.environment.strip().lower() == "production"

app = FastAPI(
    title="Customer Support SaaS",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)
maybe_install_cors_middleware(app=app, settings=settings)

chat_rate_limiter = SlidingWindowRateLimiter(
    limit=settings.chat_rate_limit_requests_per_minute,
    window_seconds=60,
)


@app.middleware("http")
async def limit_public_chat_requests(request: Request, call_next):
    """Limit repeated public chat submissions before they reach costly services."""
    if request.method == "POST" and request.url.path == "/api/v1/agents/chat":
        # Use the socket peer address. Forwarded headers are deliberately not
        # trusted here because they can be spoofed unless a trusted proxy is
        # configured explicitly.
        client_ip = request.client.host if request.client is not None else "unknown"
        allowed, retry_after = chat_rate_limiter.allow(client_ip)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many chat requests. Please wait a moment and try again."},
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)


app.include_router(agents.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(companies.router, prefix="/api/v1")
app.include_router(monitoring.router, prefix="/api/v1")
app.include_router(evaluations.router, prefix="/api/v1")
app.include_router(webhooks.router, prefix="/api/v1")
app.include_router(webhooks.legacy_router)


@app.get("/health")
async def get_health() -> dict[str, str]:
    """Liveness probe for orchestrators and local checks."""
    return {"status": "ok"}
