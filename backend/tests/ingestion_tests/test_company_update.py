"""API tests for editing agent profile metadata."""

from fastapi.testclient import TestClient


def configure_test_app(tmp_path, monkeypatch, *, user_id: str = "user_agent_edit"):
    """Build the FastAPI app with local storage and a stubbed Clerk session."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-clerk-secret")
    monkeypatch.setenv("EIVEN_SERVICE_URL", f"sqlite:///{tmp_path / 'agent-edit.db'}")
    monkeypatch.setenv("UPLOAD_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")

    from clerk_backend_api.security.types import AuthStatus, RequestState
    from src.core.clerk_auth import require_clerk_session
    from src.core.dependencies import clear_database_caches
    from src.main import app

    clear_database_caches()

    def install_user_override(active_user_id: str) -> None:
        """Swap the authenticated user without calling Clerk in tests."""

        async def stub_require_clerk_session():
            """Return a signed-in Clerk state for the active test user."""
            return RequestState(
                status=AuthStatus.SIGNED_IN,
                token="test-session",
                payload={"sub": active_user_id, "email": f"{active_user_id}@example.org"},
            )

        app.dependency_overrides[require_clerk_session] = stub_require_clerk_session

    install_user_override(user_id)
    return app, clear_database_caches, install_user_override


def create_agent(client: TestClient, *, name: str, email: str) -> dict:
    """Create an agent through the public API and return its response body."""
    response = client.post(
        "/api/v1/companies",
        json={
            "name": name,
            "email": email,
            "phone": "+254712345678",
            "description": "Initial profile.",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_agent_profile_can_be_updated(tmp_path, monkeypatch) -> None:
    """Agent name, contact details, and description can be edited in place."""
    app, clear_database_caches, _install_user_override = configure_test_app(tmp_path, monkeypatch)

    try:
        with TestClient(app) as client:
            agent = create_agent(client, name="Sahel Agent", email="sahel-old@example.org")

            response = client.patch(
                f"/api/v1/companies/{agent['id']}",
                json={
                    "name": "Sahel Peace Mediator",
                    "email": "sahel-mediator@example.org",
                    "phone": "+254 700-111-222",
                    "description": "  Supports mediation questions from trusted documents.  ",
                },
            )

            assert response.status_code == 200, response.text
            body = response.json()
            assert body["id"] == agent["id"]
            assert body["name"] == "Sahel Peace Mediator"
            assert body["email"] == "sahel-mediator@example.org"
            assert body["phone"] == "+254700111222"
            assert body["description"] == "Supports mediation questions from trusted documents."
    finally:
        app.dependency_overrides.clear()
        clear_database_caches()


def test_agent_update_rejects_duplicate_email(tmp_path, monkeypatch) -> None:
    """Editing an agent to use another agent's email returns a clean conflict."""
    app, clear_database_caches, _install_user_override = configure_test_app(tmp_path, monkeypatch)

    try:
        with TestClient(app) as client:
            first = create_agent(client, name="DRC Women Peacebuilders", email="drc@example.org")
            second = create_agent(client, name="Resource Rights Advisor", email="rights@example.org")

            response = client.patch(
                f"/api/v1/companies/{second['id']}",
                json={"email": first["email"]},
            )

            assert response.status_code == 409
            assert response.json()["detail"] == "Agent email already exists."
    finally:
        app.dependency_overrides.clear()
        clear_database_caches()


def test_agent_update_is_owner_scoped(tmp_path, monkeypatch) -> None:
    """A signed-in user cannot edit another user's agent profile."""
    app, clear_database_caches, install_user_override = configure_test_app(tmp_path, monkeypatch)

    try:
        with TestClient(app) as client:
            agent = create_agent(client, name="Owner Scoped Agent", email="owner@example.org")
            install_user_override("different_user")

            response = client.patch(
                f"/api/v1/companies/{agent['id']}",
                json={"name": "Should Not Save"},
            )

            assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        clear_database_caches()
