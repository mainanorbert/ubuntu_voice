"""Tests for the administrator agent directory."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_admin_agent_directory_paginates_and_searches_name_or_email(tmp_path, monkeypatch) -> None:
    """Admins receive stable pages and case-insensitive name/email matches only."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("EIVEN_SERVICE_URL", f"sqlite:///{tmp_path / 'admin-agents.db'}")
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.org")

    from src.core.auth import UserIdentity, require_auth_session
    from src.core.database import Base
    from src.core.dependencies import clear_database_caches, get_database_engine, get_settings
    from src.main import app
    from src.models import Company, User

    clear_database_caches()

    async def stub_require_auth_session() -> UserIdentity:
        return UserIdentity(user_id="admin", email="admin@example.org")

    app.dependency_overrides[require_auth_session] = stub_require_auth_session
    try:
        settings = get_settings()
        engine = get_database_engine(settings.database_url)
        Base.metadata.create_all(bind=engine)
        now = datetime.now(timezone.utc)
        with Session(engine) as session:
            session.add(User(id="admin", email="admin@example.org"))
            for index, (name, email) in enumerate(
                [
                    ("Peace Mediator", "mediator@example.org"),
                    ("Community Support", "support@example.org"),
                    ("Conflict Monitor", "monitor@example.org"),
                ]
            ):
                session.add(
                    Company(
                        id=f"company_{index}",
                        name=name,
                        email=email,
                        owner_id="admin",
                        created_at=now + timedelta(seconds=index),
                    )
                )
            session.commit()

        with TestClient(app) as client:
            first_page = client.get("/api/v1/companies/admin?page=1&page_size=2")
            name_search = client.get("/api/v1/companies/admin?search=mediator")
            email_search = client.get("/api/v1/companies/admin?search=SUPPORT@")

        assert first_page.status_code == 200, first_page.text
        assert first_page.json()["total"] == 3
        assert first_page.json()["total_pages"] == 2
        assert [agent["name"] for agent in first_page.json()["agents"]] == ["Conflict Monitor", "Community Support"]
        assert name_search.json()["total"] == 1
        assert name_search.json()["agents"][0]["name"] == "Peace Mediator"
        assert email_search.json()["total"] == 1
        assert email_search.json()["agents"][0]["email"] == "support@example.org"
    finally:
        app.dependency_overrides.clear()
        clear_database_caches()
