"""Owner-scoped APIs for independent RAG evaluation datasets and runs."""

from typing import Annotated

from clerk_backend_api.security.types import RequestState
from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy.orm import Session

from src.api.v1.schemas.evaluation import (
    EvaluationQuestionCreate,
    EvaluationQuestionResponse,
    EvaluationResultResponse,
    EvaluationRunResponse,
    EvaluationWorkspaceResponse,
    RetrievedSourceResponse,
)
from src.core.clerk_auth import get_authenticated_user_identity, require_clerk_session
from src.core.config import Settings
from src.core.dependencies import get_db_session, get_settings
from src.evaluations.runner import run_evaluation_background
from src.evaluations.service import (
    create_question,
    delete_question,
    get_latest_run,
    replace_latest_run,
    seed_starter_questions,
)
from src.models import EvaluationQuestion, EvaluationResult, EvaluationRun
from src.services.ingestion import get_owned_company, upsert_user

router = APIRouter(prefix="/evaluations", tags=["evaluations"])


def build_question_response(row: EvaluationQuestion) -> EvaluationQuestionResponse:
    """Serialize one evaluation question."""
    return EvaluationQuestionResponse(
        id=row.id, question=row.question, reference_answer=row.reference_answer, created_at=row.created_at
    )


def build_run_response(session: Session, run: EvaluationRun | None) -> EvaluationRunResponse | None:
    """Serialize the retained run and its current results."""
    if run is None:
        return None
    rows = session.query(EvaluationResult).filter(EvaluationResult.run_id == run.id).order_by(EvaluationResult.created_at).all()
    results = []
    for row in rows:
        sources = row.retrieved_sources if isinstance(row.retrieved_sources, list) else []
        results.append(EvaluationResultResponse(
            id=row.id, question=row.question, reference_answer=row.reference_answer,
            generated_answer=row.generated_answer,
            retrieved_sources=[RetrievedSourceResponse.model_validate(source) for source in sources],
            correctness_passed=row.correctness_passed, correctness_explanation=row.correctness_explanation,
            relevance_passed=row.relevance_passed, relevance_explanation=row.relevance_explanation,
            groundedness_passed=row.groundedness_passed, groundedness_explanation=row.groundedness_explanation,
            retrieval_relevance_passed=row.retrieval_relevance_passed,
            retrieval_relevance_explanation=row.retrieval_relevance_explanation,
            operational_error=row.operational_error,
        ))
    return EvaluationRunResponse(
        id=run.id, status=run.status, total_questions=run.total_questions,
        completed_questions=run.completed_questions, error_message=run.error_message,
        created_at=run.created_at, completed_at=run.completed_at, results=results,
    )


def get_owned_agent(session: Session, session_state: RequestState, company_id: str):
    """Resolve the authenticated owner and selected agent."""
    identity = get_authenticated_user_identity(session_state)
    user, _created = upsert_user(session, user_id=identity.user_id, email=identity.email)
    company = get_owned_company(session, company_id=company_id, owner_id=user.id)
    return user, company


@router.get("/{company_id}", response_model=EvaluationWorkspaceResponse)
async def get_evaluation_workspace(
    company_id: str,
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> EvaluationWorkspaceResponse:
    """Return an owned agent's dataset and latest run, seeding Congo Peace once."""
    _user, company = get_owned_agent(db_session, session_state, company_id)
    seed_starter_questions(db_session, company_id=company.id)
    db_session.commit()
    questions = db_session.query(EvaluationQuestion).filter(
        EvaluationQuestion.company_id == company.id
    ).order_by(EvaluationQuestion.created_at).all()
    return EvaluationWorkspaceResponse(
        questions=[build_question_response(row) for row in questions],
        latest_run=build_run_response(db_session, get_latest_run(db_session, company_id=company.id)),
    )


@router.post("/{company_id}/questions", response_model=EvaluationQuestionResponse, status_code=status.HTTP_201_CREATED)
async def post_evaluation_question(
    company_id: str,
    body: EvaluationQuestionCreate,
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> EvaluationQuestionResponse:
    """Add one test item to an owned agent's dataset."""
    _user, company = get_owned_agent(db_session, session_state, company_id)
    row = create_question(db_session, company_id=company.id, question=body.question, reference_answer=body.reference_answer)
    db_session.commit()
    db_session.refresh(row)
    return build_question_response(row)


@router.delete("/{company_id}/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_evaluation_question(
    company_id: str,
    question_id: str,
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    db_session: Annotated[Session, Depends(get_db_session)],
) -> Response:
    """Remove one test item from an owned agent's dataset."""
    _user, company = get_owned_agent(db_session, session_state, company_id)
    delete_question(db_session, company_id=company.id, question_id=question_id)
    db_session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{company_id}/runs", response_model=EvaluationRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def post_evaluation_run(
    company_id: str,
    session_state: Annotated[RequestState, Depends(require_clerk_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[Session, Depends(get_db_session)],
    background_tasks: BackgroundTasks,
) -> EvaluationRunResponse:
    """Replace the retained run and launch independent evaluation in the background."""
    _user, company = get_owned_agent(db_session, session_state, company_id)
    seed_starter_questions(db_session, company_id=company.id)
    run = replace_latest_run(db_session, company_id=company.id)
    db_session.commit()
    db_session.refresh(run)
    response = build_run_response(db_session, run)
    background_tasks.add_task(run_evaluation_background, settings=settings, run_id=run.id)
    assert response is not None
    return response
