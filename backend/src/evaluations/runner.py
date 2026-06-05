"""Background orchestration for independent per-agent RAG evaluations."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.core.config import Settings
from src.core.database import create_database_engine, create_session_factory
from src.evaluations.graders import (
    EvaluatorOutcome,
    evaluate_correctness,
    evaluate_groundedness,
    evaluate_relevance,
    evaluate_retrieval_relevance,
)
from src.models import Company, EvaluationQuestion, EvaluationResult, EvaluationRun, User
from src.services.cost_monitoring import UsageCharge, merge_usage_charges, record_user_spend
from src.services.openrouter_agent import create_openrouter_async_client
from src.services.rag_agent import run_rag_agent_for_evaluation
from src.services.rag_retrieval import build_context_from_chunks

logger = logging.getLogger(__name__)


async def _safe_grade(label: str, awaitable) -> tuple[EvaluatorOutcome | None, str | None]:
    """Run one evaluator while converting provider failures into partial results."""
    try:
        return await awaitable, None
    except Exception as exc:
        logger.error("Evaluation criterion failed: criterion=%s error_type=%s", label, type(exc).__name__)
        return None, f"{label} evaluator failed."


async def _run_evaluation(*, settings: Settings, run_id: str) -> None:
    """Execute one retained run using a dedicated background database session."""
    engine = create_database_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    client = create_openrouter_async_client(api_key=settings.openrouter_api_key, base_url=settings.openrouter_base_url)
    with session_factory() as session:
        run = session.get(EvaluationRun, run_id)
        if run is None:
            return
        company = session.get(Company, run.company_id)
        if company is None:
            run.status = "failed"
            run.error_message = "Agent no longer exists."
            session.commit()
            return
        owner = session.get(User, company.owner_id)
        questions = session.query(EvaluationQuestion).filter(EvaluationQuestion.company_id == company.id).all()
        run.status = "running"
        session.commit()
        any_errors = False
        charges: list[UsageCharge] = []

        for item in questions:
            result = EvaluationResult(run_id=run.id, question=item.question, reference_answer=item.reference_answer)
            session.add(result)
            try:
                rag = await run_rag_agent_for_evaluation(
                    async_client=client, db_session=session, company_id=company.id, company_name=company.name,
                    user_message=item.question, history=[], language="English", chat_model=settings.openrouter_model,
                    embedding_model=settings.embedding_model, embedding_dimensions=settings.embedding_dimensions,
                    top_k=settings.rag_top_k, similarity_threshold=settings.rag_similarity_threshold,
                    openrouter_api_key=settings.openrouter_api_key, openrouter_base_url=settings.openrouter_base_url,
                )
                result.generated_answer = rag.answer
                charges.extend(rag.usage_charges)
                result.retrieved_sources = [
                    {"source": (chunk.get("metadata") or {}).get("file_name", "document"), "similarity": float(chunk.get("similarity", 0))}
                    for chunk in rag.documents
                ]
                facts = build_context_from_chunks(rag.documents)
                grades = await asyncio.gather(
                    _safe_grade("correctness", evaluate_correctness(client, settings.evaluation_model, question=item.question, answer=rag.answer, reference_answer=item.reference_answer)),
                    _safe_grade("relevance", evaluate_relevance(client, settings.evaluation_model, question=item.question, answer=rag.answer)),
                    _safe_grade("groundedness", evaluate_groundedness(client, settings.evaluation_model, answer=rag.answer, facts=facts)),
                    _safe_grade("retrieval relevance", evaluate_retrieval_relevance(client, settings.evaluation_model, question=item.question, facts=facts)),
                )
                fields = ["correctness", "relevance", "groundedness", "retrieval_relevance"]
                errors: list[str] = []
                for field, (grade, error) in zip(fields, grades, strict=True):
                    if grade is not None:
                        setattr(result, f"{field}_passed", grade.passed)
                        setattr(result, f"{field}_explanation", grade.explanation)
                        if grade.usage_charge is not None:
                            charges.append(grade.usage_charge)
                    if error:
                        errors.append(error)
                if errors:
                    any_errors = True
                    result.operational_error = " ".join(errors)
            except Exception as exc:
                any_errors = True
                result.operational_error = "RAG evaluation failed for this question."
                logger.error("Evaluation question failed: run_id=%s error_type=%s", run.id, type(exc).__name__)
            run.completed_questions += 1
            session.commit()

        if charges and owner is not None:
            record_user_spend(session, user_id=owner.id, email=owner.email, charge=merge_usage_charges(charges))
        run.status = "partial" if any_errors else "completed"
        run.completed_at = datetime.now(timezone.utc)
        session.commit()
    engine.dispose()


def run_evaluation_background(*, settings: Settings, run_id: str) -> None:
    """Synchronous BackgroundTasks entrypoint for the asynchronous evaluation runner."""
    try:
        asyncio.run(_run_evaluation(settings=settings, run_id=run_id))
    except Exception as exc:
        logger.critical("Evaluation run failed: run_id=%s error_type=%s", run_id, type(exc).__name__)
        engine = create_database_engine(settings.database_url)
        with Session(engine) as session:
            run = session.get(EvaluationRun, run_id)
            if run is not None:
                run.status = "failed"
                run.error_message = "Evaluation run failed."
                run.completed_at = datetime.now(timezone.utc)
                session.commit()
        engine.dispose()
