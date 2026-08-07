"""API tests for editing agent profile metadata."""

from fastapi.testclient import TestClient


def configure_test_app(tmp_path, monkeypatch, *, user_id: str = "user_agent_edit"):
    """Build the FastAPI app with local storage and a stubbed auth session."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("EIVEN_SERVICE_URL", f"sqlite:///{tmp_path / 'agent-edit.db'}")
    monkeypatch.setenv("UPLOAD_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")

    from src.core.auth import UserIdentity, require_auth_session
    from src.core.dependencies import clear_database_caches
    from src.main import app

    clear_database_caches()

    def install_user_override(active_user_id: str) -> None:
        """Swap the authenticated user without calling an external provider."""

        async def stub_require_auth_session():
            """Return the active first-party session identity without token verification."""
            return UserIdentity(
                user_id=active_user_id,
                email=f"{active_user_id}@example.org",
            )

        app.dependency_overrides[require_auth_session] = stub_require_auth_session

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


def test_agent_creation_rejects_duplicate_name(tmp_path, monkeypatch) -> None:
    """Creating an agent with an existing name returns a clean conflict."""
    app, clear_database_caches, _install_user_override = configure_test_app(tmp_path, monkeypatch)

    try:
        with TestClient(app) as client:
            create_agent(client, name="DRC Women Peacebuilders", email="drc@example.org")

            response = client.post(
                "/api/v1/companies",
                json={"name": "DRC Women Peacebuilders", "email": "another@example.org"},
            )

            assert response.status_code == 409
            assert response.json()["detail"] == "This agent name is already in use. Choose a different name."
    finally:
        app.dependency_overrides.clear()
        clear_database_caches()


def test_agent_can_be_deleted_by_its_owner(tmp_path, monkeypatch) -> None:
    """Deleting an agent removes it from the owner's agent list."""
    app, clear_database_caches, _install_user_override = configure_test_app(tmp_path, monkeypatch)

    try:
        with TestClient(app) as client:
            agent = create_agent(client, name="Agent To Remove", email="remove@example.org")

            response = client.delete(f"/api/v1/companies/{agent['id']}")

            assert response.status_code == 204
            assert all(item["id"] != agent["id"] for item in client.get("/api/v1/companies").json())
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
