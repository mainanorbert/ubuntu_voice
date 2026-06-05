"""Persistence helpers for owner-scoped evaluation datasets and latest runs."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.models import EvaluationQuestion, EvaluationResult, EvaluationRun

MAX_EVALUATION_QUESTIONS = 50
ACTIVE_STATUSES = {"pending", "running"}
CONGO_PEACE_AGENT_ID = "0c96001c-e0cc-4f0e-b4ae-e38bc64f8add"
STARTER_QUESTIONS = [
    (
        "What are the main functions and services of La Voix des Sans Voix (VSV), and what safety considerations should be taken before reporting human rights violations publicly?",
        "VSV documents human rights abuses, advocates for detainees, and protects civic freedoms such as freedom of expression, association, and peaceful assembly. Before reporting violations publicly, individuals should consult trained human rights professionals and use secure, confidential communication channels to protect their safety and privacy.",
    ),
    (
        "How did the 1994 Rwandan Genocide contribute to the Congo War, and how can regional dialogue and reintegration be applied?",
        "After the genocide, 2 million Hutu refugees and extremist militias crossed into the DRC and started using the camps to attack Rwanda, leading to insecurity. For regional dialogue and reintegration, there is a need to establish effective programs to disarm and reintegrate combatants from the FDLR and M23.",
    ),
]


def get_latest_run(session: Session, *, company_id: str) -> EvaluationRun | None:
    """Return the single retained evaluation run for an agent."""
    return session.query(EvaluationRun).filter(EvaluationRun.company_id == company_id).one_or_none()


def assert_dataset_mutable(session: Session, *, company_id: str) -> None:
    """Reject dataset changes while the agent has an active run."""
    run = get_latest_run(session, company_id=company_id)
    if run is not None and run.status in ACTIVE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Evaluation is currently running.")


def seed_starter_questions(session: Session, *, company_id: str) -> None:
    """Seed the approved starter dataset only for the Congo Peace agent."""
    if company_id != CONGO_PEACE_AGENT_ID:
        return
    if session.query(EvaluationQuestion).filter(EvaluationQuestion.company_id == company_id).count() > 0:
        return
    for question, reference_answer in STARTER_QUESTIONS:
        session.add(EvaluationQuestion(company_id=company_id, question=question, reference_answer=reference_answer))
    session.flush()


def create_question(session: Session, *, company_id: str, question: str, reference_answer: str) -> EvaluationQuestion:
    """Add one validated test item to an agent's dataset."""
    assert_dataset_mutable(session, company_id=company_id)
    count = session.query(EvaluationQuestion).filter(EvaluationQuestion.company_id == company_id).count()
    if count >= MAX_EVALUATION_QUESTIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An agent can have at most 50 questions.")
    row = EvaluationQuestion(company_id=company_id, question=question.strip(), reference_answer=reference_answer.strip())
    session.add(row)
    session.flush()
    return row


def delete_question(session: Session, *, company_id: str, question_id: str) -> None:
    """Delete one question only when it belongs to the selected agent."""
    assert_dataset_mutable(session, company_id=company_id)
    row = session.query(EvaluationQuestion).filter(
        EvaluationQuestion.id == question_id, EvaluationQuestion.company_id == company_id
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation question not found.")
    session.delete(row)


def replace_latest_run(session: Session, *, company_id: str) -> EvaluationRun:
    """Delete the retained run and create a pending replacement from the current dataset."""
    existing = get_latest_run(session, company_id=company_id)
    if existing is not None and existing.status in ACTIVE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Evaluation is currently running.")
    questions = session.query(EvaluationQuestion).filter(EvaluationQuestion.company_id == company_id).all()
    if not questions:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Add at least one evaluation question.")
    if existing is not None:
        session.query(EvaluationResult).filter(EvaluationResult.run_id == existing.id).delete()
        session.delete(existing)
        session.flush()
    run = EvaluationRun(company_id=company_id, status="pending", total_questions=len(questions))
    session.add(run)
    session.flush()
    return run
