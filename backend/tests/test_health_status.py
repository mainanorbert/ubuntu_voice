"""Tests for the public health-check endpoint."""

from fastapi.testclient import TestClient


def test_health_status_returns_ok(tmp_path, monkeypatch):
    """Health check responds with an OK status payload."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-clerk-secret")
    monkeypatch.setenv("EIVEN_SERVICE_URL", f"sqlite:///{tmp_path / 'health.db'}")
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_KEY", "")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")

    from src.core.dependencies import clear_database_caches

    clear_database_caches()

    from src.main import app

    try:
        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        clear_database_caches()
