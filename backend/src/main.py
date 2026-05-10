"""FastAPI application entrypoint."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.api.v1.routers import agents, companies, monitoring, users
from src.core.config import Settings
from src.core.database import Base
from src.core.dependencies import get_database_engine, get_settings
from src.core.pgvector_setup import database_url_is_postgresql, ensure_pgvector_extension
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


app = FastAPI(title="Customer Support SaaS", version="0.1.0", lifespan=lifespan)
maybe_install_cors_middleware(app=app, settings=get_settings())
app.include_router(agents.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(companies.router, prefix="/api/v1")
app.include_router(monitoring.router, prefix="/api/v1")


@app.get("/health")
async def get_health() -> dict[str, str]:
    """Liveness probe for orchestrators and local checks."""
    return {"status": "ok"}