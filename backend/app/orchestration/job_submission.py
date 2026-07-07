"""Orchestrates the Job -> PlacementHistory -> Pipeline submission workflow.

This used to live entirely inside JobService.submit_candidate_to_job, which
directly instantiated and called PlacementHistoryService and PipelineService
and committed all three domains' writes in one transaction. JobService no
longer knows about either of those services (see
app/services/job_service.py JobService.create_submission_for_candidate,
which only builds the JobSubmission row). This module is now the one place
that knows the workflow spans three domains and is responsible for the
flush/commit choreography between them.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.job import Job
from app.models.job_submission import JobSubmission
from app.models.job_vendor import JobVendor
from app.schemas.auth import CurrentUser
from app.schemas.candidate import CandidateCreate
from app.schemas.job import JobSubmissionCreate, JobSubmissionResponse
from app.schemas.pipeline import PipelineCreate, PipelineStage, PipelineStatus
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService
from app.services.pipeline_service import PipelineService
from app.services.placement_history_service import PlacementHistoryService
from app.services.task_runner import dispatch_task

logger = logging.getLogger(__name__)


def submit_candidate_to_job(
    db: Session,
    *,
    job_id: UUID,
    organization_id: UUID,
    current_user: CurrentUser,
    payload: JobSubmissionCreate,
) -> JobSubmissionResponse:
    logger.info("SUBMIT_START: Job=%s Candidate=%s Org=%s", job_id, payload.candidate_id, organization_id)

    job_service = JobService(db)
    job, candidate, submission = job_service.create_submission_for_candidate(
        job_id=job_id,
        organization_id=organization_id,
        current_user=current_user,
        payload=payload,
    )

    try:
        # Flush so we can create the pipeline in the same transaction.
        db.flush()
        PlacementHistoryService(db).record_pending_submission(
            candidate_id=candidate.id,
            job_id=job.id,
            submitted_at=submission.submitted_at,
        )
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(JobSubmission).where(
                JobSubmission.job_id == job.id,
                JobSubmission.candidate_id == candidate.id,
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "DUPLICATE_SUBMISSION",
                    "existing_submission_id": str(existing.id),
                    "existing_status": existing.submission_status,
                },
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="DUPLICATE_SUBMISSION")

    # Create initial pipeline card (Phase 1 integration).
    PipelineService(db).create_pipeline(
        organization_id=organization_id,
        current_user=current_user,
        payload=PipelineCreate(
            candidate_id=candidate.id,
            job_id=job.id,
            stage=PipelineStage.APPLIED,
            status=PipelineStatus.ACTIVE,
            notes=payload.notes,
        ),
        commit=False,
    )

    try:
        # Commit JobSubmission and Pipeline together.
        db.commit()
        db.refresh(submission)
        try:
            from app.candidate_management.tasks_ats import (
                rescore_candidate_job_task,
                run_rescore_candidate_job,
            )

            dispatch_task(
                task=rescore_candidate_job_task,
                fallback=run_rescore_candidate_job,
                kwargs={
                    "organization_id": str(organization_id),
                    "candidate_id": str(candidate.id),
                    "job_id": str(job.id),
                },
            )
        except Exception as dispatch_exc:
            # Submission is already committed; never rollback here — only log dispatch noise.
            logger.warning(
                "SUBMIT_ATS_DISPATCH_FAILED org=%s job=%s candidate=%s err=%s",
                organization_id,
                job.id,
                candidate.id,
                dispatch_exc,
                exc_info=True,
            )
        res = JobSubmissionResponse.model_validate(submission)
        logger.info("SUBMIT_SUCCESS: Submission %s created", submission.id)
        return res
    except Exception as e:
        logger.error("SUBMIT_VALIDATION_ERROR: %s", e)
        raise


def vendor_submit_candidate(
    db: Session,
    *,
    job_id: UUID,
    organization_id: UUID,
    current_user: CurrentUser,
    payload: CandidateCreate,
) -> Candidate:
    """Vendor-facing self-service candidate submission (Job + Candidate + Pipeline).

    Moved out of app/routes/job.py's vendor_submit_candidate route handler:
    the vendor-role check, the job-exists check, and the "is this vendor
    actually assigned to this job" authorization check are Job/Vendor-domain
    business rules, not HTTP-layer concerns, so they belong alongside the
    existing Candidate + Pipeline creation choreography this function already
    performs.
    """
    if (current_user.role or "").strip().lower() != "vendor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: only vendors can submit candidates via this endpoint.",
        )

    user_id = UUID(current_user.user_id)

    job_exists = db.scalar(
        select(1).where(Job.id == job_id, Job.organization_id == organization_id)
    )
    if job_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    is_assigned = db.scalar(
        select(1).where(JobVendor.job_id == job_id, JobVendor.vendor_id == user_id)
    )
    if is_assigned is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vendor not assigned to this job")

    # Single DB transaction so candidate + submission pipeline are atomic.
    try:
        with db.begin():
            # Keep candidate creation rules in service layer (single source of truth).
            candidate = CandidateService(db).create_candidate(
                organization_id,
                payload,
                current_user=current_user,
                auto_commit=False,
            )

            # AIRIS Phase 0.5 Task A2: routes/orchestration must not construct
            # Pipeline ORM objects directly — delegate to
            # PipelineService.create_pipeline, which owns Pipeline
            # persistence (validation, duplicate check, audit). commit=False
            # so it flushes into this same transaction instead of committing
            # independently.
            PipelineService(db).create_pipeline(
                organization_id,
                current_user,
                PipelineCreate(
                    candidate_id=candidate.id,
                    job_id=job_id,
                    stage=PipelineStage.APPLIED,
                    status=PipelineStatus.ACTIVE,
                    notes=None,
                ),
                commit=False,
            )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pipeline already exists for this candidate and job.",
        ) from None

    return candidate
