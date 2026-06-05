"""Tests for the independent RAG evaluation dataset and judge contracts."""

import asyncio
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.core.database import Base
from src.evaluations.graders import evaluate_correctness, evaluate_groundedness, print_evaluator_comparison
from src.evaluations.service import (
    create_question,
    replace_latest_run,
)
from src.models import Company, EvaluationQuestion, EvaluationRun, User


def build_session() -> Session:
    """Create an isolated SQLite session with all evaluation tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def add_company(session: Session, *, company_id: str, owner_id: str = "owner_1") -> Company:
    """Create an owner and agent for evaluation service tests."""
    session.add(User(id=owner_id, email=None))
    company = Company(id=company_id, owner_id=owner_id, name=f"Agent {company_id}", email=f"{company_id}@example.org")
    session.add(company)
    session.commit()
    return company


def test_replacing_latest_run_retains_only_one_run() -> None:
    """Starting a new run replaces the agent's retained previous run."""
    with build_session() as session:
        company = add_company(session, company_id="agent-1")
        create_question(session, company_id=company.id, question="Question?", reference_answer="Answer.")
        first = replace_latest_run(session, company_id=company.id)
        first.status = "completed"
        session.commit()

        second = replace_latest_run(session, company_id=company.id)
        session.commit()

        runs = session.query(EvaluationRun).filter(EvaluationRun.company_id == company.id).all()
        assert len(runs) == 1
        assert runs[0].id == second.id


def test_correctness_evaluator_parses_strict_grade_and_builds_expected_prompt() -> None:
    """The OpenAI-compatible judge request returns a validated boolean grade."""
    calls: list[dict] = []

    class FakeCompletions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            message = SimpleNamespace(content='{"explanation":"Matches the reference.","passed":true}')
            return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    result = asyncio.run(
        evaluate_correctness(
            client,
            "openai/gpt-5.4",
            question="What happened?",
            answer="The expected event happened.",
            reference_answer="The expected event happened.",
        )
    )

    assert result.passed is True
    assert result.explanation == "Matches the reference."
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert "GROUND TRUTH ANSWER" in calls[0]["messages"][1]["content"]


def test_evaluator_comparison_printing_is_opt_in(capsys) -> None:
    """Exact comparison values print only when debug comparisons are enabled."""
    values = [("QUESTION", "What happened?"), ("GENERATED RESPONSE", "An answer.")]
    print_evaluator_comparison(criterion="relevance", values=values, enabled=False)
    assert capsys.readouterr().out == ""

    print_evaluator_comparison(criterion="relevance", values=values, enabled=True)
    output = capsys.readouterr().out
    assert "EVALUATION COMPARISON: RELEVANCE" in output
    assert "What happened?" in output
    assert "An answer." in output


def test_groundedness_debug_comparison_prints_question(capsys) -> None:
    """Groundedness diagnostics identify the question being evaluated."""

    class FakeCompletions:
        async def create(self, **_kwargs):
            message = SimpleNamespace(content='{"explanation":"Supported.","passed":true}')
            return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    client = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    asyncio.run(
        evaluate_groundedness(
            client,
            "openai/gpt-5.4",
            question="Which facts support this answer?",
            answer="The generated response.",
            facts="The retrieved context.",
            debug_comparisons=True,
        )
    )

    output = capsys.readouterr().out
    assert "--- QUESTION ---" in output
    assert "Which facts support this answer?" in output


def test_evaluation_workspace_is_owner_scoped(tmp_path, monkeypatch) -> None:
    """A signed-in owner cannot read another owner's evaluation workspace."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setenv("CLERK_SECRET_KEY", "test-clerk-secret")
    monkeypatch.setenv("EIVEN_SERVICE_URL", f"sqlite:///{tmp_path / 'evaluations.db'}")
    monkeypatch.setenv("UPLOAD_ROOT", str(tmp_path / "uploads"))
    monkeypatch.setenv("SUPABASE_URL", "")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")

    from clerk_backend_api.security.types import AuthStatus, RequestState
    from src.core.clerk_auth import require_clerk_session
    from src.core.dependencies import clear_database_caches
    from src.main import app

    clear_database_caches()
    active_user = {"id": "owner_a"}

    async def stub_require_clerk_session():
        return RequestState(
            status=AuthStatus.SIGNED_IN,
            token="test-session",
            payload={"sub": active_user["id"], "email": f"{active_user['id']}@example.org"},
        )

    app.dependency_overrides[require_clerk_session] = stub_require_clerk_session
    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/v1/companies",
                json={"name": "Private Evaluation Agent", "email": "private-eval@example.org"},
            )
            assert created.status_code == 201
            company_id = created.json()["id"]

            active_user["id"] = "owner_b"
            response = client.get(f"/api/v1/evaluations/{company_id}")
            assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
        clear_database_caches()
