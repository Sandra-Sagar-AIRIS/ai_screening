"""AI Screening routes.

Pattern overview
─────────────────
POST   /ai-screenings              → create + immediately kick off question generation in background
GET    /ai-screenings              → list screenings for org
GET    /ai-screenings/{id}         → full detail with Q+A+evaluations
POST   /ai-screenings/{id}/regenerate-questions → re-run question generation
PUT    /ai-screenings/{id}/answers/{question_id} → upsert one answer
POST   /ai-screenings/{id}/evaluate → trigger AI evaluation in background
POST   /ai-screenings/{id}/decision → record recruiter decision
DELETE /ai-screenings/{id}         → delete screening
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import (
    AI_SCREENING_CREATE,
    AI_SCREENING_DELETE,
    AI_SCREENING_EVALUATE,
    AI_SCREENING_READ,
    AI_SCREENING_UPDATE,
)
from app.db.session import get_db
from app.schemas.ai_screening import (
    AIScreeningCreate,
    AIScreeningDetailResponse,
    AIScreeningListItem,
    AIScreeningRecruiterDecision,
    AIScreeningResponse,
    AnswerUpsert,
    AIScreeningAnswerResponse,
    StartScreeningPayload,
    MoveStagePayload,
)
from app.schemas.auth import CurrentUser
from app.services.ai_screening_service import AIScreeningService

router = APIRouter(prefix="/ai-screenings", tags=["ai-screenings"])


def _svc(db: Session) -> AIScreeningService:
    return AIScreeningService(db)


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=AIScreeningResponse, status_code=status.HTTP_201_CREATED)
def create_screening(
    payload: AIScreeningCreate,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(AI_SCREENING_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AIScreeningResponse:
    """Create a screening and immediately start AI question generation in the background.

    The response is returned instantly with status=pending.
    Poll GET /ai-screenings/{id} until status=questions_ready.
    """
    svc = _svc(db)
    org_id = UUID(current_user.organization_id)
    screening = svc.create_screening(org_id, current_user, payload)

    # Kick off question generation asynchronously — never blocks HTTP response.
    background_tasks.add_task(
        _run_generate_questions,
        org_id=org_id,
        screening_id=screening.id,
        db_url="",
    )

    return AIScreeningResponse.model_validate(screening)


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[AIScreeningListItem])
def list_screenings(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(AI_SCREENING_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    candidate_id: UUID | None = Query(default=None),
    job_id: UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AIScreeningListItem]:
    return _svc(db).list_screenings(
        UUID(current_user.organization_id),
        candidate_id=candidate_id,
        job_id=job_id,
        status=status_filter,
        limit=limit,
        offset=offset,
    )


# ── Detail ────────────────────────────────────────────────────────────────────

@router.get("/{screening_id}", response_model=AIScreeningDetailResponse)
def get_screening(
    screening_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(AI_SCREENING_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AIScreeningDetailResponse:
    return _svc(db).get_screening_detail(UUID(current_user.organization_id), screening_id)


# ── Re-generate questions ─────────────────────────────────────────────────────

@router.post("/{screening_id}/regenerate-questions", response_model=AIScreeningResponse)
def regenerate_questions(
    screening_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(AI_SCREENING_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AIScreeningResponse:
    """Clear existing questions and regenerate. Useful after AI failure or manual retry."""
    from sqlalchemy import delete as sa_delete
    from app.models.ai_screening import AIScreeningQuestion

    svc = _svc(db)
    org_id = UUID(current_user.organization_id)
    screening = svc.get_screening(org_id, screening_id)

    # Delete existing questions (CASCADE removes answers + evaluations)
    db.execute(sa_delete(AIScreeningQuestion).where(AIScreeningQuestion.screening_id == screening_id))
    screening.status = "pending"
    db.add(screening)
    db.commit()

    background_tasks.add_task(
        _run_generate_questions,
        org_id=org_id,
        screening_id=screening_id,
        db_url="",
    )
    db.refresh(screening)
    return AIScreeningResponse.model_validate(screening)


# ── Upsert answer ─────────────────────────────────────────────────────────────

@router.put(
    "/{screening_id}/answers/{question_id}",
    response_model=AIScreeningAnswerResponse,
)
def upsert_answer(
    screening_id: UUID,
    question_id: UUID,
    payload: AnswerUpsert,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(AI_SCREENING_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AIScreeningAnswerResponse:
    answer = _svc(db).upsert_answer(
        UUID(current_user.organization_id), screening_id, question_id, payload
    )
    return AIScreeningAnswerResponse.model_validate(answer)


# ── Trigger evaluation ────────────────────────────────────────────────────────

@router.post("/{screening_id}/evaluate", response_model=AIScreeningResponse)
def evaluate_screening(
    screening_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(AI_SCREENING_EVALUATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AIScreeningResponse:
    """Trigger AI evaluation of all submitted answers. Runs in background.

    Returns immediately with status=evaluating.
    Poll GET /ai-screenings/{id} until status=completed.
    """
    svc = _svc(db)
    org_id = UUID(current_user.organization_id)
    screening = svc.get_screening(org_id, screening_id)

    background_tasks.add_task(
        _run_evaluation,
        org_id=org_id,
        screening_id=screening_id,
        db_url="",
    )

    screening.status = "evaluating"
    db.add(screening)
    db.commit()
    db.refresh(screening)
    return AIScreeningResponse.model_validate(screening)


# ── Recruiter decision ────────────────────────────────────────────────────────

@router.post("/{screening_id}/decision", response_model=AIScreeningResponse)
def record_decision(
    screening_id: UUID,
    payload: AIScreeningRecruiterDecision,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(AI_SCREENING_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AIScreeningResponse:
    screening = _svc(db).record_recruiter_decision(
        UUID(current_user.organization_id),
        screening_id,
        decision=payload.decision.value,
        notes=payload.notes,
    )
    return AIScreeningResponse.model_validate(screening)


# ── Delete ────────────────────────────────────────────────────────────────────

@router.delete("/{screening_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_screening(
    screening_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(AI_SCREENING_DELETE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    _svc(db).delete_screening(UUID(current_user.organization_id), screening_id)


# ── Start (create + optional pipeline move) ───────────────────────────────────

@router.post("/start", response_model=AIScreeningResponse, status_code=status.HTTP_201_CREATED)
def start_screening(
    payload: StartScreeningPayload,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(AI_SCREENING_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AIScreeningResponse:
    """Convenience endpoint: create screening + optionally move pipeline stage to ai_screening.

    Mirrors POST /ai-screenings but accepts a pipeline_id to move the candidate's
    pipeline entry in one atomic step, eliminating two round-trips from the frontend.
    """
    svc = _svc(db)
    org_id = UUID(current_user.organization_id)

    # 1. Move pipeline stage if requested
    if payload.move_pipeline_stage and payload.pipeline_id:
        from app.services.pipeline_service import PipelineService
        from app.schemas.pipeline import PipelineUpdate
        try:
            PipelineService(db).update_pipeline(
                payload.pipeline_id, org_id, current_user, PipelineUpdate(stage="ai_screening")
            )
        except Exception:
            # Non-fatal — screening is more important than stage move
            logger.warning("start_screening: pipeline stage move failed for %s", payload.pipeline_id)

    # 2. Create the screening
    create_payload = AIScreeningCreate(
        candidate_id=payload.candidate_id,
        job_id=payload.job_id,
        screening_type=payload.screening_type,
    )
    screening = svc.create_screening(org_id, current_user, create_payload)

    # 3. Kick off question generation in background
    background_tasks.add_task(
        _run_generate_questions,
        org_id=org_id,
        screening_id=screening.id,
        db_url="",
    )

    return AIScreeningResponse.model_validate(screening)


# ── Retry (re-trigger failed question generation or evaluation) ───────────────

@router.post("/{screening_id}/retry", response_model=AIScreeningResponse)
def retry_screening(
    screening_id: UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(AI_SCREENING_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AIScreeningResponse:
    """Re-trigger the last failed background task.

    - If status is 'failed' and no questions exist → re-run question generation.
    - If status is 'failed' and questions exist → re-run evaluation.
    - If status is 'questions_ready' → also re-run evaluation (convenient shortcut).
    """
    from app.models.ai_screening import AIScreeningQuestion

    svc = _svc(db)
    org_id = UUID(current_user.organization_id)
    screening = svc.get_screening(org_id, screening_id)

    question_count = db.scalar(
        select(func.count()).select_from(AIScreeningQuestion).where(
            AIScreeningQuestion.screening_id == screening_id
        )
    ) or 0

    if question_count == 0:
        # Re-run question generation
        screening.status = "pending"
        db.add(screening)
        db.commit()
        background_tasks.add_task(
            _run_generate_questions,
            org_id=org_id,
            screening_id=screening_id,
            db_url="",
        )
    else:
        # Re-run evaluation
        screening.status = "evaluating"
        db.add(screening)
        db.commit()
        background_tasks.add_task(
            _run_evaluation,
            org_id=org_id,
            screening_id=screening_id,
            db_url="",
        )

    db.refresh(screening)
    return AIScreeningResponse.model_validate(screening)


# ── Move pipeline stage based on screening result ─────────────────────────────

@router.post("/{screening_id}/move-stage", response_model=AIScreeningResponse)
def move_pipeline_stage(
    screening_id: UUID,
    payload: MoveStagePayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(AI_SCREENING_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AIScreeningResponse:
    """Move the candidate's pipeline entry to the given stage.

    Typically called after a recruiter decides to advance or reject from the
    screening review panel.  Returns the screening row for easy frontend update.
    """
    from app.services.pipeline_service import PipelineService
    from app.schemas.pipeline import PipelineUpdate, PipelineStage

    org_id = UUID(current_user.organization_id)
    svc = _svc(db)
    screening = svc.get_screening(org_id, screening_id)

    # Validate the stage value
    valid_stages = {s.value for s in PipelineStage}
    if payload.stage not in valid_stages:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Invalid stage '{payload.stage}'. Valid: {sorted(valid_stages)}")

    PipelineService(db).update_pipeline(
        payload.pipeline_id, org_id, current_user, PipelineUpdate(stage=payload.stage)
    )

    return AIScreeningResponse.model_validate(screening)


# ── Background task helpers ───────────────────────────────────────────────────
# Each creates its own DB session so it can run independently of the request
# session (which will have been closed by the time the background task runs).

def _run_generate_questions(*, org_id: UUID, screening_id: UUID, db_url: str) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        AIScreeningService(db).generate_questions(org_id, screening_id)
    finally:
        db.close()


def _run_evaluation(*, org_id: UUID, screening_id: UUID, db_url: str) -> None:
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        AIScreeningService(db).run_evaluation(org_id, screening_id)
    finally:
        db.close()
