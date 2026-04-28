from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.pipeline import Pipeline
from app.schemas.auth import CurrentUser
from app.schemas.interview import InterviewCreate, InterviewStatus, InterviewUpdate
from app.services.access_scope_service import AccessScopeService
from app.services.pipeline_service import PipelineService


def _assert_scheduled_not_in_past(scheduled_at: datetime) -> None:
    """Reject datetimes strictly before current UTC time."""
    now = datetime.now(UTC)
    if scheduled_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scheduled_at must not be in the past (times are interpreted in UTC).",
        )


def _validate_status_transition(current: str, new: str) -> None:
    if current == new:
        return

    terminal = frozenset({
        InterviewStatus.COMPLETED.value,
        InterviewStatus.CANCELLED.value,
        InterviewStatus.NO_SHOW.value,
    })
    if current in terminal:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid status transition: interviews in '{current}' status cannot be changed. "
                "Allowed targets from scheduled: completed, cancelled, no_show, rescheduled. "
                "From rescheduled: scheduled only."
            ),
        )

    if current == InterviewStatus.SCHEDULED.value:
        allowed = frozenset({
            InterviewStatus.COMPLETED.value,
            InterviewStatus.CANCELLED.value,
            InterviewStatus.NO_SHOW.value,
            InterviewStatus.RESCHEDULED.value,
        })
        if new not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid status transition from 'scheduled' to '{new}'. "
                    "Allowed: completed, cancelled, no_show, rescheduled."
                ),
            )
        return

    if current == InterviewStatus.RESCHEDULED.value:
        if new != InterviewStatus.SCHEDULED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid status transition from 'rescheduled' to '{new}'. "
                    "Only allowed transition: rescheduled → scheduled."
                ),
            )
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid status transition from '{current}' to '{new}'.",
    )


class InterviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._scope = AccessScopeService(db)
        self._pipelines = PipelineService(db)

    def create_interview(self, organization_id: UUID, current_user: CurrentUser, payload: InterviewCreate) -> Interview:
        self._pipelines.get_pipeline_by_id(payload.pipeline_id, organization_id, current_user)
        _assert_scheduled_not_in_past(payload.scheduled_at)

        interview = Interview(
            organization_id=organization_id,
            pipeline_id=payload.pipeline_id,
            scheduled_at=payload.scheduled_at,
            status=payload.status.value,
            interviewer_name=payload.interviewer_name.strip() if payload.interviewer_name else None,
            notes=payload.notes,
        )
        self.db.add(interview)
        self.db.commit()
        self.db.refresh(interview)
        return interview

    def list_interviews(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        *,
        limit: int = 50,
        offset: int = 0,
        pipeline_id: UUID | None = None,
    ) -> list[Interview]:
        stmt: Select[tuple[Interview]] = select(Interview).where(Interview.organization_id == organization_id)
        if pipeline_id is not None:
            stmt = stmt.where(Interview.pipeline_id == pipeline_id)
        allowed_job_ids = self._scope.allowed_job_ids(current_user)
        if self._scope.is_client_user(current_user):
            if not allowed_job_ids:
                return []
            stmt = stmt.where(
                Interview.pipeline_id.in_(
                    select(Pipeline.id).where(Pipeline.job_id.in_(allowed_job_ids))
                )
            )
        stmt = stmt.order_by(Interview.scheduled_at.desc()).offset(offset).limit(limit)
        return list(self.db.scalars(stmt))

    def get_interview_by_id(self, interview_id: UUID, organization_id: UUID, current_user: CurrentUser) -> Interview:
        stmt: Select[tuple[Interview]] = select(Interview).where(
            Interview.id == interview_id,
            Interview.organization_id == organization_id,
        )
        allowed_job_ids = self._scope.allowed_job_ids(current_user)
        if self._scope.is_client_user(current_user):
            stmt = stmt.where(
                Interview.pipeline_id.in_(
                    select(Pipeline.id).where(Pipeline.job_id.in_(allowed_job_ids))
                )
            )
        interview = self.db.scalar(stmt)
        if interview is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found.",
            )
        return interview

    def update_interview(
        self,
        interview_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: InterviewUpdate,
    ) -> Interview:
        interview = self.get_interview_by_id(interview_id, organization_id, current_user)

        update_data = payload.model_dump(exclude_unset=True)
        if "pipeline_id" in update_data:
            new_pipeline_id = update_data.pop("pipeline_id")
            if new_pipeline_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="pipeline_id cannot be null.",
                )
            self._pipelines.get_pipeline_by_id(new_pipeline_id, organization_id, current_user)
            update_data["pipeline_id"] = new_pipeline_id

        if "scheduled_at" in update_data and update_data["scheduled_at"] is not None:
            _assert_scheduled_not_in_past(update_data["scheduled_at"])

        if "status" in update_data and update_data["status"] is not None:
            new_status = update_data["status"].value
            _validate_status_transition(interview.status, new_status)
            update_data["status"] = new_status

        if "interviewer_name" in update_data and update_data["interviewer_name"] is not None:
            update_data["interviewer_name"] = str(update_data["interviewer_name"]).strip() or None

        for field, value in update_data.items():
            setattr(interview, field, value)

        self.db.add(interview)
        self.db.commit()
        self.db.refresh(interview)
        return interview
