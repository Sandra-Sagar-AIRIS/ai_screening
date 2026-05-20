"""Sourcing routes — AI-SOURCE-001.

POST   /sourcing/sessions            Start a new sourcing session (202)
GET    /sourcing/sessions            List sessions for org (paginated)
GET    /sourcing/sessions/{id}       Session detail
GET    /sourcing/sessions/{id}/status  Lightweight polling
GET    /sourcing/sessions/{id}/results Paginated results
PATCH  /sourcing/sessions/{id}/results/{rid}  Update action
"""
from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.sourcing_session import SourcingResult, SourcingSession
from app.schemas.auth import CurrentUser
from app.schemas.sourcing import (
    PaginatedSourcingResults,
    StartSourcingSessionRequest,
    StartSourcingSessionResponse,
    SourcingResultOut,
    SourcingSessionOut,
    SourcingSessionStatusOut,
    UpdateResultActionRequest,
)
from app.services.sourcing.query_generator import SourcingQueryGenerator
from app.services.task_runner import dispatch_task

router = APIRouter()
logger = logging.getLogger(__name__)

_ALLOWED_ROLES = {"admin", "recruiter"}


def _require_sourcing_access(current_user: CurrentUser) -> CurrentUser:
    """Admin or recruiter only."""
    role = (current_user.role or "").strip().lower()
    if role not in _ALLOWED_ROLES:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    return current_user


def _get_session_for_user(
    db: Session,
    session_id: UUID,
    org_id: UUID,
    user_id: str,
    role: str,
) -> SourcingSession:
    """Fetch session with org scoping. Recruiters see only their own sessions."""
    stmt = select(SourcingSession).where(
        SourcingSession.id == session_id,
        SourcingSession.organization_id == org_id,
    )
    if role.strip().lower() != "admin":
        stmt = stmt.where(SourcingSession.created_by == UUID(user_id))
    row = db.scalar(stmt)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    return row


# ── POST /sessions ────────────────────────────────────────────────────────────


@router.post(
    "/sessions",
    response_model=StartSourcingSessionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_sourcing_session(
    payload: StartSourcingSessionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> StartSourcingSessionResponse:
    _require_sourcing_access(current_user)
    org_id = UUID(current_user.organization_id)

    # Generate query snapshot from JD
    generator = SourcingQueryGenerator()
    query = generator.generate(payload.jd_text, overrides=payload.overrides)

    session_row = SourcingSession(
        organization_id=org_id,
        job_id=payload.job_id,
        created_by=UUID(current_user.user_id),
        status="pending",
        query_snapshot={
            "title": query.title,
            "skills": query.skills,
            "keywords": query.keywords,
            "location": query.location,
            "experience_min": query.experience_min,
            "experience_max": query.experience_max,
        },
        providers_used=payload.providers,
        total_results=0,
    )
    db.add(session_row)
    db.commit()
    db.refresh(session_row)

    logger.info(
        "sourcing.session.created",
        extra={
            "session_id": str(session_row.id),
            "job_id": str(payload.job_id) if payload.job_id else None,
            "org_id": str(org_id),
            "created_by": current_user.user_id,
            "providers": payload.providers,
        },
    )

    # Dispatch background runner
    from app.services.sourcing.runner import run_sourcing_session

    dispatch_task(
        task=None,
        fallback=run_sourcing_session,
        kwargs={
            "session_id": str(session_row.id),
            "org_id": str(org_id),
            "jd_text": payload.jd_text,
        },
    )

    return StartSourcingSessionResponse(session_id=session_row.id)


# ── GET /sessions ─────────────────────────────────────────────────────────────


@router.get("/sessions", response_model=list[SourcingSessionOut])
def list_sourcing_sessions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    job_id: UUID | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> list[SourcingSession]:
    _require_sourcing_access(current_user)
    org_id = UUID(current_user.organization_id)
    role = (current_user.role or "").strip().lower()

    stmt = select(SourcingSession).where(
        SourcingSession.organization_id == org_id,
    )
    if role != "admin":
        stmt = stmt.where(SourcingSession.created_by == UUID(current_user.user_id))
    if job_id:
        stmt = stmt.where(SourcingSession.job_id == job_id)
    stmt = stmt.order_by(SourcingSession.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt).all())


# ── GET /sessions/{session_id} ────────────────────────────────────────────────


@router.get("/sessions/{session_id}", response_model=SourcingSessionOut)
def get_sourcing_session(
    session_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SourcingSession:
    _require_sourcing_access(current_user)
    return _get_session_for_user(
        db, session_id,
        org_id=UUID(current_user.organization_id),
        user_id=current_user.user_id,
        role=current_user.role or "",
    )


# ── GET /sessions/{session_id}/status ────────────────────────────────────────


@router.get("/sessions/{session_id}/status", response_model=SourcingSessionStatusOut)
def get_session_status(
    session_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SourcingSessionStatusOut:
    _require_sourcing_access(current_user)
    row = _get_session_for_user(
        db, session_id,
        org_id=UUID(current_user.organization_id),
        user_id=current_user.user_id,
        role=current_user.role or "",
    )
    return SourcingSessionStatusOut(
        session_id=row.id,
        status=row.status,
        total_results=row.total_results,
    )


# ── GET /sessions/{session_id}/results ───────────────────────────────────────


@router.get("/sessions/{session_id}/results", response_model=PaginatedSourcingResults)
def list_session_results(
    session_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    action: str | None = Query(default=None, pattern="^(pending|shortlisted|rejected|imported)$"),
    source: str | None = Query(default=None),
    ats_tier: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> PaginatedSourcingResults:
    _require_sourcing_access(current_user)
    org_id = UUID(current_user.organization_id)

    # Verify session access
    _get_session_for_user(
        db, session_id,
        org_id=org_id,
        user_id=current_user.user_id,
        role=current_user.role or "",
    )

    stmt = select(SourcingResult).where(
        SourcingResult.session_id == session_id,
        SourcingResult.organization_id == org_id,
    )
    if action:
        stmt = stmt.where(SourcingResult.action == action)
    if source:
        stmt = stmt.where(SourcingResult.source == source)
    if ats_tier:
        stmt = stmt.where(SourcingResult.ats_tier == ats_tier)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.scalar(count_stmt) or 0

    stmt = stmt.order_by(SourcingResult.ats_score.desc().nullslast()).offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(stmt).all())

    return PaginatedSourcingResults(
        items=items,  # type: ignore[arg-type]
        total=total,
        page=page,
        page_size=page_size,
        has_more=(page * page_size) < total,
    )


# ── PATCH /sessions/{session_id}/results/{result_id} ─────────────────────────


@router.patch("/sessions/{session_id}/results/{result_id}", response_model=SourcingResultOut)
def update_result_action(
    session_id: UUID,
    result_id: UUID,
    payload: UpdateResultActionRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SourcingResult:
    _require_sourcing_access(current_user)
    org_id = UUID(current_user.organization_id)

    # Verify session access
    _get_session_for_user(
        db, session_id,
        org_id=org_id,
        user_id=current_user.user_id,
        role=current_user.role or "",
    )

    result = db.scalar(
        select(SourcingResult).where(
            SourcingResult.id == result_id,
            SourcingResult.session_id == session_id,
            SourcingResult.organization_id == org_id,
        )
    )
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Result not found.")

    # Conflict guard: rejected result cannot be shortlisted/imported
    if result.action == "rejected" and payload.action in ("shortlisted", "imported"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot shortlist or import a rejected candidate.",
        )

    # Idempotent: same action is a no-op
    if result.action == payload.action:
        return result

    # Apply action
    if payload.action == "imported":
        _handle_import(db, result, org_id, UUID(current_user.user_id))

    result.action = payload.action
    if payload.action == "rejected" and payload.reject_reason:
        result.reject_reason = payload.reject_reason
        raw = dict(result.raw_data or {})
        raw["reject_reason"] = payload.reject_reason
        result.raw_data = raw

    db.commit()
    db.refresh(result)

    # Audit log
    log_event = f"sourcing.result.{payload.action}"
    logger.info(
        log_event,
        extra={
            "session_id": str(session_id),
            "result_id": str(result_id),
            "org_id": str(org_id),
            "acted_by": current_user.user_id,
            "pipeline_stage_id": str(payload.pipeline_stage_id) if payload.pipeline_stage_id else None,
        },
    )
    return result


def _handle_import(db: Session, result: SourcingResult, org_id: UUID, imported_by: UUID) -> None:
    """Import result as a Candidate, then optionally add to pipeline."""
    from app.services.sourcing.importer import CandidateImportService

    importer = CandidateImportService(db)
    importer.import_result(result, org_id, imported_by)
