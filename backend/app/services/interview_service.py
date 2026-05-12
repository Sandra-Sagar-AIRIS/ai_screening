from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.interview import (
    Interview,
    InterviewFeedback,
    InterviewParticipant,
    InterviewerProfile,
    InterviewerSkill,
    InterviewerAvailability,
)
from app.models.job import Job
from app.models.pipeline import Pipeline
from app.schemas.auth import CurrentUser
from app.schemas.interview import (
    InterviewCreate,
    InterviewFeedbackCreate,
    InterviewParticipantCreate,
    InterviewStatus,
    InterviewUpdate,
    InterviewerProfileCreate,
    QueueInterviewResponse,
)
from app.services.access_scope_service import AccessScopeService
from app.services.interview_notification_service import InterviewNotificationService
from app.services.pipeline_service import PipelineService


ELIGIBLE_STAGES: frozenset[str] = frozenset({"screening", "interview", "offer", "placed"})

# Statuses shown in the interviewer queue
QUEUE_STATUSES: frozenset[str] = frozenset({
    InterviewStatus.PENDING_PANEL.value,
    InterviewStatus.SCHEDULED.value,
})


def _assert_scheduled_not_in_past(scheduled_at: datetime) -> None:
    now = datetime.now(UTC)
    if scheduled_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="scheduled_at must not be in the past (times are interpreted in UTC).",
        )


def _assert_stage_eligible(pipeline: Pipeline) -> None:
    if pipeline.stage not in ELIGIBLE_STAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Interview scheduling requires the candidate to be at stage "
                f"'screening', 'interview', 'offer', or 'placed'. "
                f"Current stage is '{pipeline.stage}'."
            ),
        )


_VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    InterviewStatus.SCHEDULED.value: frozenset({
        InterviewStatus.PENDING_PANEL.value,
        InterviewStatus.CONFIRMED.value,
        InterviewStatus.PANEL_CONFIRMED.value,
        InterviewStatus.IN_PROGRESS.value,
        InterviewStatus.COMPLETED.value,
        InterviewStatus.CANCELLED.value,
        InterviewStatus.NO_SHOW.value,
        InterviewStatus.RESCHEDULED.value,
        InterviewStatus.FEEDBACK_PENDING.value,
    }),
    InterviewStatus.PENDING_PANEL.value: frozenset({
        InterviewStatus.PANEL_CONFIRMED.value,
        InterviewStatus.SCHEDULED.value,   # downgrade if needed
        InterviewStatus.CANCELLED.value,
        InterviewStatus.RESCHEDULED.value,
    }),
    InterviewStatus.PANEL_CONFIRMED.value: frozenset({
        InterviewStatus.IN_PROGRESS.value,
        InterviewStatus.COMPLETED.value,
        InterviewStatus.CANCELLED.value,
        InterviewStatus.NO_SHOW.value,
        InterviewStatus.RESCHEDULED.value,
        InterviewStatus.FEEDBACK_PENDING.value,
    }),
    InterviewStatus.IN_PROGRESS.value: frozenset({
        InterviewStatus.COMPLETED.value,
        InterviewStatus.NO_SHOW.value,
        InterviewStatus.CANCELLED.value,
    }),
    InterviewStatus.CONFIRMED.value: frozenset({
        InterviewStatus.IN_PROGRESS.value,
        InterviewStatus.PANEL_CONFIRMED.value,
        InterviewStatus.COMPLETED.value,
        InterviewStatus.CANCELLED.value,
        InterviewStatus.NO_SHOW.value,
        InterviewStatus.RESCHEDULED.value,
        InterviewStatus.FEEDBACK_PENDING.value,
    }),
    InterviewStatus.RESCHEDULED.value: frozenset({
        InterviewStatus.SCHEDULED.value,
        InterviewStatus.PENDING_PANEL.value,
    }),
    InterviewStatus.FEEDBACK_PENDING.value: frozenset({
        InterviewStatus.COMPLETED.value,
        InterviewStatus.FEEDBACK_SUBMITTED.value,
    }),
    # Terminal + near-terminal
    InterviewStatus.COMPLETED.value: frozenset({
        InterviewStatus.FEEDBACK_PENDING.value,
    }),
    InterviewStatus.FEEDBACK_SUBMITTED.value: frozenset(),
    InterviewStatus.CANCELLED.value: frozenset(),
    InterviewStatus.NO_SHOW.value: frozenset(),
}


def _validate_status_transition(current: str, new: str) -> None:
    if current == new:
        return
    allowed = _VALID_TRANSITIONS.get(current, frozenset())
    if new not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Invalid status transition from '{current}' to '{new}'. "
                f"Allowed: {', '.join(sorted(allowed)) or 'none (terminal state)'}."
            ),
        )


class InterviewService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._scope = AccessScopeService(db)
        self._pipelines = PipelineService(db)
        self._notify = InterviewNotificationService()

    # ── Scoped query base ────────────────────────────────────────────────

    def _base_interview_stmt(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> Select[tuple[Interview]]:
        stmt = select(Interview).where(Interview.organization_id == organization_id)
        if self._scope.is_scoped_user(current_user):
            stmt = stmt.where(
                Interview.pipeline_id.in_(
                    select(Pipeline.id).where(
                        Pipeline.job_id.in_(self._scope.allowed_job_ids_subquery(current_user))
                    )
                )
            )
        return stmt

    # ── Core CRUD ────────────────────────────────────────────────────────

    def create_interview(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: InterviewCreate,
    ) -> Interview:
        pipeline = self._pipelines.get_pipeline_by_id(payload.pipeline_id, organization_id, current_user)
        _assert_stage_eligible(pipeline)
        _assert_scheduled_not_in_past(payload.scheduled_at)

        if payload.duration_minutes is not None and payload.duration_minutes <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="duration_minutes must be a positive integer.",
            )

        interview = Interview(
            organization_id=organization_id,
            pipeline_id=payload.pipeline_id,
            candidate_id=pipeline.candidate_id,
            job_id=pipeline.job_id,
            interview_type=payload.interview_type.value if payload.interview_type else None,
            meeting_type=payload.meeting_type.value if payload.meeting_type else None,
            scheduled_at=payload.scheduled_at,
            duration_minutes=payload.duration_minutes,
            meeting_link=payload.meeting_link,
            location=payload.location,
            status=payload.status.value,
            interviewer_name=payload.interviewer_name.strip() if payload.interviewer_name else None,
            notes=payload.notes,
            created_by=UUID(current_user.user_id),
        )
        self.db.add(interview)
        self.db.commit()
        self.db.refresh(interview)

        self._notify.on_interview_scheduled(interview.id, organization_id)
        return interview

    def list_interviews(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        *,
        limit: int = 50,
        offset: int = 0,
        pipeline_id: UUID | None = None,
        candidate_id: UUID | None = None,
        job_id: UUID | None = None,
        status_filter: str | None = None,
    ) -> list[Interview]:
        stmt = self._base_interview_stmt(organization_id, current_user)

        if pipeline_id is not None:
            stmt = stmt.where(Interview.pipeline_id == pipeline_id)
        if candidate_id is not None:
            stmt = stmt.where(Interview.candidate_id == candidate_id)
        if job_id is not None:
            stmt = stmt.where(Interview.job_id == job_id)
        if status_filter is not None:
            stmt = stmt.where(Interview.status == status_filter)

        stmt = stmt.order_by(Interview.scheduled_at.desc()).offset(offset).limit(limit)
        return list(self.db.scalars(stmt))

    def get_interview_by_id(
        self,
        interview_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> Interview:
        stmt = self._base_interview_stmt(organization_id, current_user).where(
            Interview.id == interview_id,
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
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="pipeline_id cannot be null.")
            self._pipelines.get_pipeline_by_id(new_pipeline_id, organization_id, current_user)
            update_data["pipeline_id"] = new_pipeline_id

        if "scheduled_at" in update_data and update_data["scheduled_at"] is not None:
            _assert_scheduled_not_in_past(update_data["scheduled_at"])

        prev_status = interview.status
        if "status" in update_data and update_data["status"] is not None:
            new_status = update_data["status"].value
            _validate_status_transition(interview.status, new_status)
            update_data["status"] = new_status

        if "interview_type" in update_data and update_data["interview_type"] is not None:
            update_data["interview_type"] = update_data["interview_type"].value

        if "meeting_type" in update_data and update_data["meeting_type"] is not None:
            update_data["meeting_type"] = update_data["meeting_type"].value

        if "interviewer_name" in update_data and update_data["interviewer_name"] is not None:
            update_data["interviewer_name"] = str(update_data["interviewer_name"]).strip() or None

        for field, value in update_data.items():
            setattr(interview, field, value)

        self.db.add(interview)
        self.db.commit()
        self.db.refresh(interview)

        new_status_val = interview.status
        if prev_status != new_status_val:
            if new_status_val == InterviewStatus.CONFIRMED.value:
                self._notify.on_interview_confirmed(interview.id, organization_id)
            elif new_status_val == InterviewStatus.RESCHEDULED.value:
                self._notify.on_interview_rescheduled(interview.id, organization_id)
            elif new_status_val == InterviewStatus.CANCELLED.value:
                self._notify.on_interview_cancelled(interview.id, organization_id)

        return interview

    def delete_interview(
        self,
        interview_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> None:
        interview = self.get_interview_by_id(interview_id, organization_id, current_user)
        self.db.delete(interview)
        self.db.commit()

    # ── Queue ────────────────────────────────────────────────────────────

    def get_queue(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        *,
        limit: int = 50,
        offset: int = 0,
        round_type: str | None = None,
        job_id: UUID | None = None,
    ) -> list[QueueInterviewResponse]:
        """Return interviews needing panelists, enriched with candidate/job names and participant count."""

        # Subquery: count accepted participants per interview
        pcount_sq = (
            select(
                InterviewParticipant.interview_id.label("interview_id"),
                func.count(InterviewParticipant.id).label("cnt"),
            )
            .where(InterviewParticipant.status == "accepted")
            .group_by(InterviewParticipant.interview_id)
            .subquery("pcount")
        )

        stmt = (
            select(
                Interview,
                Candidate.first_name,
                Candidate.last_name,
                Job.title,
                func.coalesce(pcount_sq.c.cnt, 0).label("participant_count"),
            )
            .join(Candidate, Interview.candidate_id == Candidate.id, isouter=True)
            .join(Job, Interview.job_id == Job.id, isouter=True)
            .outerjoin(pcount_sq, Interview.id == pcount_sq.c.interview_id)
            .where(Interview.organization_id == organization_id)
            .where(Interview.status.in_(QUEUE_STATUSES))
            .order_by(Interview.scheduled_at.asc())
        )

        if round_type:
            stmt = stmt.where(Interview.interview_type == round_type)
        if job_id:
            stmt = stmt.where(Interview.job_id == job_id)

        # AccessScope filtering for scoped users
        if self._scope.is_scoped_user(current_user):
            stmt = stmt.where(
                Interview.pipeline_id.in_(
                    select(Pipeline.id).where(
                        Pipeline.job_id.in_(self._scope.allowed_job_ids_subquery(current_user))
                    )
                )
            )

        rows = self.db.execute(stmt.offset(offset).limit(limit)).all()

        results: list[QueueInterviewResponse] = []
        for interview, first_name, last_name, job_title, participant_count in rows:
            resp = QueueInterviewResponse.model_validate(interview)
            resp.candidate_first_name = first_name
            resp.candidate_last_name = last_name
            resp.job_title = job_title
            resp.participant_count = int(participant_count or 0)
            results.append(resp)
        return results

    # ── My Interviews ────────────────────────────────────────────────────

    def get_my_interviews(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Interview]:
        """Return interviews where the current user is a participant."""
        user_uuid = UUID(current_user.user_id)
        stmt = (
            select(Interview)
            .join(
                InterviewParticipant,
                InterviewParticipant.interview_id == Interview.id,
            )
            .where(Interview.organization_id == organization_id)
            .where(InterviewParticipant.user_id == user_uuid)
            .where(InterviewParticipant.status != "declined")
            .order_by(Interview.scheduled_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    # ── Panel management ─────────────────────────────────────────────────

    def claim_interview(
        self,
        interview_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> InterviewParticipant:
        """Interviewer self-assigns as lead panelist. Advances status to panel_confirmed."""
        interview = self.get_interview_by_id(interview_id, organization_id, current_user)

        if interview.status not in QUEUE_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot claim an interview with status '{interview.status}'.",
            )

        user_uuid = UUID(current_user.user_id)

        # Prevent duplicate claim
        existing = self.db.scalar(
            select(InterviewParticipant).where(
                InterviewParticipant.interview_id == interview_id,
                InterviewParticipant.user_id == user_uuid,
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already claimed this interview.",
            )

        participant = InterviewParticipant(
            organization_id=organization_id,
            interview_id=interview_id,
            user_id=user_uuid,
            role="lead",
            participant_role="lead",
            status="accepted",
            joined_at=datetime.now(UTC),
        )
        self.db.add(participant)

        # Advance status: first lead claim → panel_confirmed
        if interview.status in {InterviewStatus.PENDING_PANEL.value, InterviewStatus.SCHEDULED.value}:
            interview.status = InterviewStatus.PANEL_CONFIRMED.value
            self.db.add(interview)

        self.db.commit()
        self.db.refresh(participant)
        return participant

    def add_participant(
        self,
        interview_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: InterviewParticipantCreate,
    ) -> InterviewParticipant:
        """Recruiter adds any user as a panelist."""
        self.get_interview_by_id(interview_id, organization_id, current_user)

        # Prevent duplicate
        existing = self.db.scalar(
            select(InterviewParticipant).where(
                InterviewParticipant.interview_id == interview_id,
                InterviewParticipant.user_id == payload.user_id,
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a participant in this interview.",
            )

        participant = InterviewParticipant(
            organization_id=organization_id,
            interview_id=interview_id,
            user_id=payload.user_id,
            role=payload.participant_role.value,
            participant_role=payload.participant_role.value,
            status="invited",
        )
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant

    def list_participants(
        self,
        interview_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> list[InterviewParticipant]:
        self.get_interview_by_id(interview_id, organization_id, current_user)
        stmt = (
            select(InterviewParticipant)
            .where(InterviewParticipant.interview_id == interview_id)
            .order_by(InterviewParticipant.created_at.asc())
        )
        return list(self.db.scalars(stmt))

    def remove_participant(
        self,
        interview_id: UUID,
        participant_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> None:
        self.get_interview_by_id(interview_id, organization_id, current_user)
        participant = self.db.scalar(
            select(InterviewParticipant).where(
                InterviewParticipant.id == participant_id,
                InterviewParticipant.interview_id == interview_id,
            )
        )
        if participant is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found.")
        self.db.delete(participant)
        self.db.commit()

    # ── Feedback ─────────────────────────────────────────────────────────

    def create_feedback(
        self,
        interview_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: InterviewFeedbackCreate,
    ) -> InterviewFeedback:
        interview = self.get_interview_by_id(interview_id, organization_id, current_user)

        non_feedback_statuses = {InterviewStatus.CANCELLED.value, InterviewStatus.NO_SHOW.value}
        if interview.status in non_feedback_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot submit feedback for an interview with status '{interview.status}'.",
            )

        reviewer_id = UUID(current_user.user_id)

        existing = self.db.scalar(
            select(InterviewFeedback).where(
                InterviewFeedback.interview_id == interview_id,
                InterviewFeedback.reviewer_id == reviewer_id,
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You have already submitted feedback for this interview.",
            )

        now = datetime.now(UTC)
        feedback = InterviewFeedback(
            interview_id=interview_id,
            reviewer_id=reviewer_id,
            technical_score=payload.technical_score,
            communication_score=payload.communication_score,
            problem_solving_score=payload.problem_solving_score,
            culture_fit_score=payload.culture_fit_score,
            rating=payload.rating,
            recommendation=payload.recommendation.value if payload.recommendation else None,
            strengths=payload.strengths,
            weaknesses=payload.weaknesses,
            notes=payload.notes,
            submitted_at=now,
        )
        self.db.add(feedback)

        if interview.status == InterviewStatus.COMPLETED.value:
            pass
        else:
            _validate_status_transition(interview.status, InterviewStatus.FEEDBACK_PENDING.value)
            interview.status = InterviewStatus.FEEDBACK_PENDING.value
            self.db.add(interview)

        self.db.commit()
        self.db.refresh(feedback)

        self._notify.on_feedback_submitted(interview_id, organization_id)
        return feedback

    def get_feedback(
        self,
        interview_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> list[InterviewFeedback]:
        self.get_interview_by_id(interview_id, organization_id, current_user)
        stmt = (
            select(InterviewFeedback)
            .where(InterviewFeedback.interview_id == interview_id)
            .order_by(InterviewFeedback.created_at.asc())
        )
        return list(self.db.scalars(stmt))

    # ── Interviewer profiles ──────────────────────────────────────────────

    def upsert_my_profile(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: InterviewerProfileCreate,
    ) -> InterviewerProfile:
        user_uuid = UUID(current_user.user_id)
        profile = self.db.scalar(
            select(InterviewerProfile).where(
                InterviewerProfile.organization_id == organization_id,
                InterviewerProfile.user_id == user_uuid,
            )
        )
        if profile is None:
            profile = InterviewerProfile(
                organization_id=organization_id,
                user_id=user_uuid,
            )
            self.db.add(profile)

        profile.title = payload.title
        profile.department = payload.department
        profile.is_active = payload.is_active
        profile.max_interviews_per_day = payload.max_interviews_per_day
        profile.timezone = payload.timezone
        profile.bio = payload.bio

        self.db.flush()

        # Replace skills
        self.db.execute(
            InterviewerSkill.__table__.delete().where(
                InterviewerSkill.interviewer_profile_id == profile.id
            )
        )
        for skill_name in payload.skills:
            self.db.add(InterviewerSkill(interviewer_profile_id=profile.id, skill=skill_name.strip()))

        self.db.commit()
        self.db.refresh(profile)
        return profile

    def get_my_profile(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> InterviewerProfile | None:
        user_uuid = UUID(current_user.user_id)
        return self.db.scalar(
            select(InterviewerProfile).where(
                InterviewerProfile.organization_id == organization_id,
                InterviewerProfile.user_id == user_uuid,
            )
        )

    def get_profile_skills(self, profile_id: UUID) -> list[str]:
        rows = self.db.scalars(
            select(InterviewerSkill.skill).where(
                InterviewerSkill.interviewer_profile_id == profile_id
            )
        )
        return list(rows)
