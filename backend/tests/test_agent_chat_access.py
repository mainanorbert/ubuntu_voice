"""Access rules for public web-agent chat."""

import asyncio
from types import SimpleNamespace

from fastapi import BackgroundTasks
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.api.v1.routers import agents
from src.api.v1.schemas.agent import AgentChatRequest
from src.core.auth import UserIdentity
from src.core.database import Base
from src.models import Company, User


def test_authenticated_user_can_chat_with_another_owners_public_agent(monkeypatch) -> None:
    """Signing in must not turn the public chat agent list into an owner-only list."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                User(id="visitor", email="visitor@example.org"),
                User(id="agent-owner", email="owner@example.org"),
                Company(
                    id="public-agent",
                    owner_id="agent-owner",
                    name="Community Support",
                    email="support@example.org",
                ),
            ]
        )
        session.commit()

        selected_agent_ids: list[str] = []

        async def fake_run_rag_agent(**kwargs):
            selected_agent_ids.append(kwargs["company_id"])
            return "Welcome.", False, []

        async def unexpected_alert(**_kwargs):
            raise AssertionError("A visitor chatting with another owner's agent must not trigger owner alerts.")

        monkeypatch.setattr(agents, "run_rag_agent", fake_run_rag_agent)
        monkeypatch.setattr(agents, "maybe_send_conflict_alert", unexpected_alert)

        settings = SimpleNamespace(
            database_url="sqlite:///:memory:",
            guardrail_max_input_tokens=500,
            guardrail_token_encoding="cl100k_base",
            openrouter_api_key="test-key",
            openrouter_base_url="https://example.invalid/v1",
            openrouter_model="test-model",
            embedding_model="test-embedding-model",
            embedding_dimensions=1536,
            rag_top_k=5,
            rag_similarity_threshold=0.25,
            guardrail_phone_country_code="254",
        )
        response = asyncio.run(
            agents.post_agent_chat(
                body=AgentChatRequest(company_id="public-agent", message="How can I get help?"),
                session_state=UserIdentity(user_id="visitor", email="visitor@example.org"),
                settings=settings,
                client=SimpleNamespace(),
                db_session=session,
                background_tasks=BackgroundTasks(),
            )
        )

    assert response.reply == "Welcome."
    assert selected_agent_ids == ["public-agent"]
