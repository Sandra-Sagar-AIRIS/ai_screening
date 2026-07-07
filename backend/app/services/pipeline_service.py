from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.pipeline import Pipeline, PipelineStageHistory, PipelineStatusHistory
from app.models.job import Job
from app.core.config import get_settings
from app.schemas.auth import CurrentUser
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineSortBy,
    PipelineSortDir,
    PipelineStage,
    PipelineStageTransitionRequest,
    PipelineStatus,
    PipelineStatusChangeRequest,
    PipelineUpdate,
    WithdrawPipelineRequest,
)
from app.services.access_scope_service import AccessScopeService

logger = logging.getLogger(__name__)

# ── PIPE-002: Valid stage transitions ─────────────────────────────────────────
# Terminal stages (placed, rejected) have no outgoing transitions.
VALID_TRANSITIONS: dict[str, frozenset[str]] = {
    PipelineStage.APPLIED.value:      frozenset({PipelineStage.AI_INTERVIEW.value, PipelineStage.REJECTED.value}),
    PipelineStage.AI_INTERVIEW.value: frozenset({PipelineStage.INTERVIEW.value, PipelineStage.REJECTED.value}),
    PipelineStage.INTERVIEW.value:    frozenset({PipelineStage.OFFER.value, PipelineStage.REJECTED.value}),
    PipelineStage.OFFER.value:        frozenset({PipelineStage.PLACED.value, PipelineStage.REJECTED.value}),
    PipelineStage.PLACED.value:       frozenset(),
    PipelineStage.REJECTED.value:     frozenset(),
}


class PipelineService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._scope = AccessScopeService(db)

    def _get_candidate_or_404(
        self,
        candidate_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> Candidate:
        """Validate a candidate exists (and is visible to this user) without
        instantiating CandidateService, mirroring how create_pipeline already
        validates Job directly to avoid circular construction between
        JobService/CandidateService <-> PipelineService.

        Mirrors CandidateService.get_candidate_by_id's org-scope, soft-delete,
        and client/vendor visibility rules exactly, so this read-only check
        behaves identically to the previous delegated call.
        """
        stmt: Select[tuple[Candidate]] = select(Candidate).where(
            Candidate.id == candidate_id,
            or_(
                Candidate.organization_id == organization_id,
                Candidate.org_id == organization_id,
            ),
            Candidate.is_deleted.is_(False),
            Candidate.deleted_at.is_(None),
        )
        if self._scope.is_client_user(current_user):
            stmt = stmt.where(
                Candidate.id.in_(
                    select(Pipeline.candidate_id).where(
                        Pipeline.job_id.in_(self._scope.allowed_job_ids_subquery(current_user))
                    )
                )
            )
        elif self._scope.is_vendor_user(current_user):
            stmt = stmt.where(Candidate.created_by == UUID(current_user.user_id))
        candidate = self.db.scalar(stmt)
        if candidate is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found.")
        return candidate

    def create_pipeline(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: PipelineCreate,
        *,
        commit: bool = True,
    ) -> Pipeline:
        self._get_candidate_or_404(payload.candidate_id, organization_id, current_user)

        # Validate job exists (and scope it for client users) without instantiating JobService
        # to avoid circular construction between JobService <-> PipelineService.
        stmt = select(Job).where(Job.id == payload.job_id, Job.organization_id == organization_id)
        if self._scope.is_client_user(current_user):
            # Filter by allowed job IDs via SQL subquery (no Python list materialization).
            stmt = stmt.where(Job.id.in_(self._scope.allowed_job_ids_subquery(current_user)))

        job = self.db.scalar(stmt)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

        existing = self.db.scalar(
            select(Pipeline.id).where(
                Pipeline.organization_id == organization_id,
                Pipeline.candidate_id == payload.candidate_id,
                Pipeline.job_id == payload.job_id,
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pipeline already exists for this candidate and job.",
            )

        pipeline = Pipeline(
            organization_id=organization_id,
            candidate_id=payload.candidate_id,
            job_id=payload.job_id,
            stage=payload.stage.value,
            status=payload.status.value,
            notes=payload.notes,
        )
        self.db.add(pipeline)
        try:
            # Flush instead of committing so callers can atomically create
            # JobSubmission + Pipeline in a single transaction.
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pipeline already exists for this candidate and job.",
            ) from None
        if commit:
            self.db.commit()
        self.db.refresh(pipeline)
        return pipeline

    def sync_stage_for_candidate(
        self,
        *,
        organization_id: UUID,
        candidate_id: UUID,
        job_id: UUID,
        new_stage: str,
        actor_user_id: UUID | None,
        reason: str,
    ) -> Pipeline:
        """Get-or-create a pipeline and apply a system-driven stage sync.

        AIRIS Phase 0.5 Task A1: this is the only path through which the
        Candidate domain may affect Pipeline state (see
        app.orchestration.candidate_pipeline_sync) — it replaces a prior
        implementation where candidate_management directly constructed and
        mutated Pipeline ORM objects.

        This is deliberately NOT transition_stage: system-driven callers
        (candidate-management sync, imports, automated workflows) report
        the candidate's actual current stage, which may differ from the
        pipeline's by more than one step. Recording the real transition
        that occurred — in one PipelineStageHistory row — is preferred over
        forcing a walk through transition_stage's adjacent-only
        VALID_TRANSITIONS to fabricate intermediate hops that never
        happened. Recruiter-driven changes continue to go through
        transition_stage/change_pipeline_status, which still enforce
        VALID_TRANSITIONS exactly as before — this method does not touch
        or relax that validation.

        actor_user_id=None marks a system-driven change; there is no
        PipelineStageHistory.actor_user_id value for "System" (it's a
        nullable UUID column), so the caller's `reason` text should say so
        explicitly — that's the audit-trail record of who/what made the
        change when there's no real user id to attach.

        No notification/email side effects are fired here — those exist to
        tell a candidate their stage changed via a recruiter action
        (COMM-005), and firing them for every internal sync would be a new,
        unrequested candidate-facing behavior change. Only the internal
        PipelineStageHistory audit row is written.
        """
        job_exists = self.db.scalar(
            select(Job.id).where(Job.id == job_id, Job.organization_id == organization_id)
        )
        if job_exists is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected job does not exist for this organization.",
            )

        try:
            with self.db.begin_nested():
                pipeline = self.db.scalar(
                    select(Pipeline).where(
                        Pipeline.organization_id == organization_id,
                        Pipeline.candidate_id == candidate_id,
                        Pipeline.job_id == job_id,
                    )
                )
                if pipeline is None:
                    pipeline = Pipeline(
                        organization_id=organization_id,
                        candidate_id=candidate_id,
                        job_id=job_id,
                        stage=new_stage,
                        status="active",
                        notes=reason,
                    )
                    self.db.add(pipeline)
                    self.db.flush()
                else:
                    self._apply_system_stage_change(pipeline, organization_id, new_stage, actor_user_id, reason)
        except IntegrityError:
            existing = self.db.scalar(
                select(Pipeline).where(
                    Pipeline.organization_id == organization_id,
                    Pipeline.candidate_id == candidate_id,
                    Pipeline.job_id == job_id,
                )
            )
            if existing is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Duplicate pipeline entry detected for candidate and job.",
                ) from None
            pipeline = existing
            self._apply_system_stage_change(pipeline, organization_id, new_stage, actor_user_id, reason)
        except SQLAlchemyError:
            logger.exception(
                "pipeline.sync_stage_for_candidate.failed",
                extra={"candidate_id": str(candidate_id), "job_id": str(job_id), "stage": new_stage},
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pipeline sync failed for this candidate submission.",
            ) from None

        self.db.commit()
        self.db.refresh(pipeline)
        return pipeline

    def _apply_system_stage_change(
        self,
        pipeline: Pipeline,
        organization_id: UUID,
        new_stage: str,
        actor_user_id: UUID | None,
        reason: str,
    ) -> None:
        """Write the PipelineStageHistory audit row and mutate the pipeline
        in place, for a system-driven stage sync. No-ops (writes no history
        row) if the stage isn't actually changing, so a sync call that finds
        nothing new to report doesn't pollute the audit trail."""
        previous_stage = pipeline.stage
        if previous_stage == new_stage:
            return

        history = PipelineStageHistory(
            pipeline_id=pipeline.id,
            organization_id=organization_id,
            previous_stage=previous_stage,
            new_stage=new_stage,
            actor_user_id=actor_user_id,
            reason=reason,
            transitioned_at=datetime.now(UTC),
        )
        self.db.add(history)

        pipeline.stage = new_stage
        pipeline.stage_updated_at = datetime.now(UTC)
        if new_stage in (PipelineStage.PLACED.value, PipelineStage.REJECTED.value):
            pipeline.status = PipelineStatus.CLOSED.value
        self.db.add(pipeline)

    def _build_pipeline_filter_stmt(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        *,
        job_id: UUID | None = None,
        candidate_id: UUID | None = None,
        client_id: UUID | None = None,
        stage: PipelineStage | None = None,
        pipeline_status: PipelineStatus | None = None,
    ) -> Select:
        """Return a base SELECT statement with all org-scope and filter predicates applied.

        client_id filter: joins to the jobs table and filters by jobs.client_id.
        This is additive with job_id (both can be specified simultaneously).
        """
        stmt: Select = select(Pipeline).where(Pipeline.organization_id == organization_id)
        if job_id is not None:
            stmt = stmt.where(Pipeline.job_id == job_id)
        if candidate_id is not None:
            stmt = stmt.where(Pipeline.candidate_id == candidate_id)
        if client_id is not None:
            # Join to jobs to filter by client_id — no explicit FK on Pipeline.
            stmt = stmt.join(Job, Job.id == Pipeline.job_id).where(Job.client_id == client_id)
        if stage is not None:
            stmt = stmt.where(Pipeline.stage == stage.value)
        if pipeline_status is not None:
            stmt = stmt.where(Pipeline.status == pipeline_status.value)
        if self._scope.is_scoped_user(current_user):
            stmt = stmt.where(Pipeline.job_id.in_(self._scope.allowed_job_ids_subquery(current_user)))
        return stmt

    def list_pipelines(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        *,
        limit: int = 50,
        offset: int = 0,
        job_id: UUID | None = None,
        candidate_id: UUID | None = None,
        client_id: UUID | None = None,
        stage: PipelineStage | None = None,
        pipeline_status: PipelineStatus | None = None,
        sort_by: PipelineSortBy = PipelineSortBy.CREATED_AT,
        sort_dir: PipelineSortDir = PipelineSortDir.DESC,
    ) -> list[Pipeline]:
        stmt = self._build_pipeline_filter_stmt(
            organization_id,
            current_user,
            job_id=job_id,
            candidate_id=candidate_id,
            client_id=client_id,
            stage=stage,
            pipeline_status=pipeline_status,
        )
        order_col = Pipeline.stage_updated_at if sort_by == PipelineSortBy.STAGE_UPDATED_AT else Pipeline.created_at
        stmt = stmt.order_by(order_col.asc() if sort_dir == PipelineSortDir.ASC else order_col.desc())
        stmt = stmt.offset(offset).limit(limit)
        pipelines = list(self.db.scalars(stmt))
        logger.info(
            "Pipeline list fetched",
            extra={
                "organization_id": str(organization_id),
                "job_id": str(job_id) if job_id else None,
                "candidate_id": str(candidate_id) if candidate_id else None,
                "count": len(pipelines),
            },
        )
        return pipelines

    def list_pipelines_paginated(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        *,
        limit: int = 50,
        offset: int = 0,
        job_id: UUID | None = None,
        candidate_id: UUID | None = None,
        client_id: UUID | None = None,
        stage: PipelineStage | None = None,
        pipeline_status: PipelineStatus | None = None,
        sort_by: PipelineSortBy = PipelineSortBy.CREATED_AT,
        sort_dir: PipelineSortDir = PipelineSortDir.DESC,
    ) -> tuple[list[Pipeline], int, dict[str, int]]:
        """PIPE-004: Return (pipelines, total_count, stage_counts).

        - ``total_count`` is the full count matching all filters (before pagination).
        - ``stage_counts`` is a per-stage breakdown across ALL filters EXCEPT the
          stage filter itself, giving callers visibility into the full distribution.
        - ``client_id`` filters pipelines whose linked job belongs to that client.
        """
        # ── 1. Filtered page ──────────────────────────────────────────────────
        paginated_stmt = self._build_pipeline_filter_stmt(
            organization_id,
            current_user,
            job_id=job_id,
            candidate_id=candidate_id,
            client_id=client_id,
            stage=stage,
            pipeline_status=pipeline_status,
        )
        order_col = Pipeline.stage_updated_at if sort_by == PipelineSortBy.STAGE_UPDATED_AT else Pipeline.created_at
        paginated_stmt = paginated_stmt.order_by(
            order_col.asc() if sort_dir == PipelineSortDir.ASC else order_col.desc()
        ).offset(offset).limit(limit)
        pipelines = list(self.db.scalars(paginated_stmt))

        # ── 2. Total count (same filters, no pagination) ──────────────────────
        count_stmt = self._build_pipeline_filter_stmt(
            organization_id,
            current_user,
            job_id=job_id,
            candidate_id=candidate_id,
            client_id=client_id,
            stage=stage,
            pipeline_status=pipeline_status,
        )
        total: int = self.db.scalar(
            select(func.count()).select_from(count_stmt.subquery())
        ) or 0

        # ── 3. Stage counts (all filters EXCEPT stage for full facet view) ────
        stage_count_base = self._build_pipeline_filter_stmt(
            organization_id,
            current_user,
            job_id=job_id,
            candidate_id=candidate_id,
            client_id=client_id,
            stage=None,            # intentionally omit stage filter
            pipeline_status=pipeline_status,
        )
        # Use the subquery's own columns — referencing Pipeline.stage / Pipeline.id
        # directly after .select_from(subquery) creates a cross-join in SQLAlchemy.
        sub = stage_count_base.subquery()
        stage_count_stmt = (
            select(sub.c.stage, func.count(sub.c.id).label("cnt"))
            .group_by(sub.c.stage)
        )
        stage_counts: dict[str, int] = {
            row.stage: row.cnt for row in self.db.execute(stage_count_stmt)
        }

        logger.info(
            "Pipeline paginated list fetched",
            extra={
                "organization_id": str(organization_id),
                "total": total,
                "returned": len(pipelines),
                "stage_counts": stage_counts,
            },
        )
        return pipelines, total, stage_counts

    def list_pipeline_candidates_for_job(
        self,
        job_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[tuple[UUID, Candidate]]:
        """
        Pipelines for a single job with candidate rows (one round-trip in SQL).
        Enforces the same org + access-scope rules as list_pipelines + candidate visibility.
        """
        stmt: Select[tuple[UUID, Candidate]] = (
            select(Pipeline.id, Candidate)
            .join(Candidate, Candidate.id == Pipeline.candidate_id)
            .where(
                Pipeline.organization_id == organization_id,
                Pipeline.job_id == job_id,
                Candidate.is_deleted.is_(False),
            )
        )
        if self._scope.is_scoped_user(current_user):
            stmt = stmt.where(Pipeline.job_id.in_(self._scope.allowed_job_ids_subquery(current_user)))
        if self._scope.is_vendor_user(current_user):
            stmt = stmt.where(Candidate.created_by == UUID(current_user.user_id))

        stmt = stmt.order_by(Pipeline.created_at.desc()).offset(offset).limit(limit)
        rows = self.db.execute(stmt).all()
        return [(row[0], row[1]) for row in rows]

    def get_pipeline_by_id(self, pipeline_id: UUID, organization_id: UUID, current_user: CurrentUser | None = None) -> Pipeline:
        logger.info(
            "Pipeline lookup requested",
            extra={"pipeline_id": str(pipeline_id), "organization_id": str(organization_id)},
        )
        stmt: Select[tuple[Pipeline]] = select(Pipeline).where(
            Pipeline.id == pipeline_id,
            Pipeline.organization_id == organization_id,
        )
        if current_user is not None and self._scope.is_scoped_user(current_user):
            stmt = stmt.where(Pipeline.job_id.in_(self._scope.allowed_job_ids_subquery(current_user)))
        pipeline = self.db.scalar(stmt)
        if pipeline is None:
            other_org_pipeline = self.db.scalar(select(Pipeline.organization_id).where(Pipeline.id == pipeline_id))
            mismatch = other_org_pipeline is not None
            logger.warning(
                "Pipeline lookup failed",
                extra={
                    "pipeline_id": str(pipeline_id),
                    "organization_id": str(organization_id),
                    "exists_other_org": mismatch,
                    "owner_organization_id": str(other_org_pipeline) if other_org_pipeline else None,
                },
            )
            settings = get_settings()
            if settings.debug:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "error": "Pipeline not found",
                        "hint": "Pipeline may belong to another organization or token mismatch",
                        "pipeline_id": str(pipeline_id),
                        "organization_id": str(organization_id),
                    },
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pipeline not found.",
            )
        return pipeline

    def update_pipeline(
        self,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: PipelineUpdate,
    ) -> Pipeline:
        pipeline = self.get_pipeline_by_id(pipeline_id, organization_id, current_user)

        update_data = payload.model_dump(exclude_unset=True)
        if "stage" in update_data and update_data["stage"] is not None:
            update_data["stage"] = update_data["stage"].value
        if "status" in update_data and update_data["status"] is not None:
            update_data["status"] = update_data["status"].value

        for field, value in update_data.items():
            setattr(pipeline, field, value)

        self.db.add(pipeline)
        self.db.commit()
        self.db.refresh(pipeline)
        return pipeline

    # Backward-compatible alias for existing callers.
    def update_pipeline_stage(
        self,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: PipelineUpdate,
    ) -> Pipeline:
        return self.update_pipeline(pipeline_id, organization_id, current_user, payload)

    def list_all_pipelines_debug(self, *, limit: int = 200, offset: int = 0) -> list[Pipeline]:
        stmt: Select[tuple[Pipeline]] = (
            select(Pipeline).order_by(Pipeline.created_at.desc()).offset(offset).limit(limit)
        )
        return list(self.db.scalars(stmt))

    # ── PIPE-002: Controlled stage transition ─────────────────────────────────

    def transition_stage(
        self,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: PipelineStageTransitionRequest,
        *,
        commit: bool = True,
    ) -> Pipeline:
        """
        Validate and apply a stage transition. Pipeline persistence only —
        does not touch PlacementHistory (see
        app.orchestration.pipeline_transitions.transition_pipeline_stage,
        which calls this with commit=False, then PlacementHistoryService,
        then commits both together).

        Raises:
            422 — if the requested transition is not valid from the current stage.
            422 — if rejecting without a sufficient reason (enforced by Pydantic schema).
            404 — if the pipeline is not found.

        `commit=False` mirrors create_pipeline's `commit` parameter: flushes
        into the same open transaction and defers the actual commit (and the
        best-effort notification, which only makes sense once the change is
        durably committed) to the caller.
        """
        pipeline = self.get_pipeline_by_id(pipeline_id, organization_id, current_user)

        current_stage = pipeline.stage
        new_stage = payload.stage.value
        allowed_targets = VALID_TRANSITIONS.get(current_stage, frozenset())

        if new_stage not in allowed_targets:
            allowed_display = ", ".join(sorted(allowed_targets)) if allowed_targets else "none (terminal stage)"
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Cannot transition from '{current_stage}' to '{new_stage}'. "
                    f"Allowed transitions: {allowed_display}."
                ),
            )

        # Record history before mutating the pipeline row.
        history = PipelineStageHistory(
            pipeline_id=pipeline.id,
            organization_id=organization_id,
            previous_stage=current_stage,
            new_stage=new_stage,
            actor_user_id=UUID(current_user.user_id) if current_user.user_id else None,
            reason=payload.reason,
            transitioned_at=datetime.now(UTC),
        )
        self.db.add(history)

        # Apply stage change; auto-close terminal stages.
        # PIPE-004: record when the stage was last updated for sort-by-stage-updated.
        pipeline.stage = new_stage
        pipeline.stage_updated_at = datetime.now(UTC)
        if new_stage in (PipelineStage.PLACED.value, PipelineStage.REJECTED.value):
            pipeline.status = PipelineStatus.CLOSED.value

        self.db.add(pipeline)
        self.db.flush()
        stage_history_id = history.id
        if commit:
            self.db.commit()
        self.db.refresh(pipeline)

        if commit:
            # These are only safe to fire once the transition is durably
            # committed (the notification does its own internal commit, and
            # dispatches real candidate emails). A caller using commit=False
            # to coordinate this with another domain's write is responsible
            # for calling run_post_transition_side_effects itself once its
            # own combined commit has actually happened.
            self.run_post_transition_side_effects(
                pipeline,
                organization_id=organization_id,
                current_user=current_user,
                previous_stage=current_stage,
                new_stage=new_stage,
                reason=payload.reason,
                stage_history_id=stage_history_id,
            )

        return pipeline

    def run_post_transition_side_effects(
        self,
        pipeline: Pipeline,
        *,
        organization_id: UUID,
        current_user: CurrentUser,
        previous_stage: str,
        new_stage: str,
        reason: str | None,
        stage_history_id: UUID,
    ) -> None:
        """Best-effort notification + AI-interview auto-create for a stage
        change that has already been durably committed.

        Split out of transition_stage so a caller that coordinates the
        stage change with another domain's write (e.g. PlacementHistory, via
        transition_stage(commit=False)) can invoke these side effects itself
        once its own combined commit has actually landed — see
        app.orchestration.pipeline_transitions.transition_pipeline_stage.
        """
        actor_user_id = UUID(current_user.user_id) if current_user.user_id else None

        # COMM-005: best-effort notification — commit already happened so this
        # must NEVER raise; any exception is swallowed and logged.
        try:
            _notify_stage_change(
                db=self.db,
                pipeline=pipeline,
                organization_id=organization_id,
                previous_stage=previous_stage,
                new_stage=new_stage,
                actor_user_id=actor_user_id,
                reason=reason,
                stage_history_id=stage_history_id,
            )
        except Exception:
            logger.warning(
                "pipeline.notify_stage_change.failed pipeline_id=%s — suppressed",
                pipeline.id,
                exc_info=True,
            )

        logger.info(
            "pipeline.stage_transition pipeline_id=%s %s→%s actor=%s",
            pipeline.id,
            previous_stage,
            new_stage,
            current_user.user_id,
        )

        # ── AI Interview: auto-create when candidate enters AI interview stage ──
        # PipelineService does not import or instantiate AIScreeningService
        # directly — this goes through app.orchestration.screening_pipeline,
        # the same module that already carries the reverse (Screening ->
        # Pipeline) direction.
        if new_stage == PipelineStage.AI_INTERVIEW.value:
            try:
                from app.orchestration.screening_pipeline import (
                    auto_create_screening_for_pipeline,
                )
                auto_create_screening_for_pipeline(
                    self.db,
                    organization_id=organization_id,
                    candidate_id=pipeline.candidate_id,
                    job_id=pipeline.job_id,
                    pipeline_id=pipeline.id,
                    created_by=actor_user_id,
                )
            except Exception:
                logger.warning(
                    "pipeline.ai_interview_auto_create.failed pipeline_id=%s — suppressed",
                    pipeline.id,
                    exc_info=True,
                )

    def get_stage_history(
        self,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> list[PipelineStageHistory]:
        """Return the full ordered stage-transition history for a pipeline."""
        # Access check — raises 404 if not found / not accessible.
        self.get_pipeline_by_id(pipeline_id, organization_id, current_user)

        return list(
            self.db.scalars(
                select(PipelineStageHistory)
                .where(
                    PipelineStageHistory.pipeline_id == pipeline_id,
                    PipelineStageHistory.organization_id == organization_id,
                )
                .order_by(PipelineStageHistory.transitioned_at)
            ).all()
        )

    # ── PIPE-003: Status tracking ─────────────────────────────────────────────

    def change_pipeline_status(
        self,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: PipelineStatusChangeRequest,
        *,
        commit: bool = True,
    ) -> Pipeline:
        """
        PIPE-003: Apply a deliberate status change with full audit trail.

        Raises:
            409  — if the requested status equals the current status (no-op).
            403  — if a non-admin attempts to reopen a closed/placed pipeline.

        `commit=False` lets a caller (e.g. an orchestrator coordinating this
        status change with a write in another domain, such as candidate
        archival) flush this change into the same open transaction and defer
        the actual commit to itself — mirrors create_pipeline's `commit`
        parameter. The best-effort notification only fires when this call
        commits; a caller that defers the commit is responsible for the
        state actually landing durably before anything downstream reacts to it.
        """
        pipeline = self.get_pipeline_by_id(pipeline_id, organization_id, current_user)

        current_status = pipeline.status
        new_status = payload.status.value

        if current_status == new_status:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Pipeline status is already '{current_status}'.",
            )

        # Prevent re-opening a closed pipeline unless the caller is an admin.
        if current_status == PipelineStatus.CLOSED.value and not _is_admin(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators can reopen a closed pipeline.",
            )

        now = datetime.now(UTC)
        history = PipelineStatusHistory(
            pipeline_id=pipeline.id,
            organization_id=organization_id,
            previous_status=current_status,
            new_status=new_status,
            actor_user_id=UUID(current_user.user_id) if current_user.user_id else None,
            reason=payload.reason,
            changed_at=now,
        )
        self.db.add(history)

        pipeline.status = new_status
        pipeline.status_changed_at = now
        self.db.add(pipeline)
        self.db.flush()
        if commit:
            self.db.commit()
        self.db.refresh(pipeline)

        if commit:
            # COMM-005: best-effort notification — commit already happened.
            try:
                _notify_status_change(
                    db=self.db,
                    pipeline=pipeline,
                    previous_status=current_status,
                    new_status=new_status,
                    actor_user_id=UUID(current_user.user_id) if current_user.user_id else None,
                    reason=payload.reason,
                )
            except Exception:
                logger.warning(
                    "pipeline.notify_status_change.failed pipeline_id=%s — suppressed",
                    pipeline_id,
                    exc_info=True,
                )

        logger.info(
            "pipeline.status_change pipeline_id=%s %s→%s actor=%s",
            pipeline_id,
            current_status,
            new_status,
            current_user.user_id,
        )
        return pipeline

    def withdraw_pipeline(
        self,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
        payload: WithdrawPipelineRequest,
    ) -> Pipeline:
        """
        PIPE-003: Withdraw a pipeline (candidate-requested removal).

        Delegates to change_pipeline_status with status=WITHDRAWN.
        Exposed as a dedicated endpoint so callers don't need to know
        the internal PipelineStatus enum.
        """
        return self.change_pipeline_status(
            pipeline_id,
            organization_id,
            current_user,
            PipelineStatusChangeRequest(
                status=PipelineStatus.WITHDRAWN,
                reason=payload.reason,
            ),
        )

    def get_status_history(
        self,
        pipeline_id: UUID,
        organization_id: UUID,
        current_user: CurrentUser,
    ) -> list[PipelineStatusHistory]:
        """Return the full ordered status-change history for a pipeline (PIPE-003)."""
        self.get_pipeline_by_id(pipeline_id, organization_id, current_user)

        return list(
            self.db.scalars(
                select(PipelineStatusHistory)
                .where(
                    PipelineStatusHistory.pipeline_id == pipeline_id,
                    PipelineStatusHistory.organization_id == organization_id,
                )
                .order_by(PipelineStatusHistory.changed_at)
            ).all()
        )

    # ── CAND-006: Candidate merge support ───────────────────────────────────────

    def reassign_candidate(
        self,
        *,
        from_candidate_id: UUID,
        to_candidate_id: UUID,
        organization_id: UUID,
    ) -> int:
        """Repoint every Pipeline row from one candidate to another (candidate merge).

        This is an identity correction, not a stage transition: no
        PipelineStageHistory/PlacementHistory row is written and no
        notification fires, since neither stage nor status actually changes.
        Called only from app.orchestration for a candidate-merge — this is
        the sole path through which the Candidate domain may mutate a
        Pipeline row's candidate_id (mirrors sync_stage_for_candidate being
        the sole path for system-driven stage writes).

        A durable audit trail specifically for merges (who merged what, and
        that these pipelines were reassigned as a result) is not implemented
        here — see CandidateMergeService's module docstring for that open
        product-policy question.
        """
        result = self.db.execute(
            update(Pipeline)
            .where(
                Pipeline.candidate_id == from_candidate_id,
                Pipeline.organization_id == organization_id,
            )
            .values(candidate_id=to_candidate_id)
        )
        self.db.flush()
        return result.rowcount or 0


# ── Internal helpers ──────────────────────────────────────────────────────────

def _is_admin(current_user: CurrentUser) -> bool:
    return (getattr(current_user, "role", "") or "").lower() == "admin"


# ── COMM-005 helpers ───────────────────────────────────────────────────────────

def _notify_stage_change(
    *,
    db: Session,
    pipeline: Pipeline,
    organization_id: UUID,
    previous_stage: str,
    new_stage: str,
    actor_user_id: UUID | None,
    reason: str | None,
    stage_history_id: UUID,
) -> None:
    """
    COMM-005: Fire a best-effort notification on stage change.

    Records a timeline interaction synchronously (via CandidateManagementService,
    which owns the CandidateInteraction write — see
    CandidateManagementService.record_system_interaction), then dispatches
    automated candidate email delivery on a background thread (AIR-570/572).
    """
    from app.candidate_management.models import InteractionType  # noqa: PLC0415
    from app.candidate_management.service import CandidateManagementService  # noqa: PLC0415
    from app.services.pipeline_stage_notification_service import (  # noqa: PLC0415
        run_pipeline_stage_email_notification,
    )
    from app.services.task_runner import dispatch_task  # noqa: PLC0415

    note = f"Stage changed: {previous_stage} → {new_stage}"
    if reason:
        note += f"\nReason: {reason}"

    stage_metadata: dict[str, str | None] = {
        "pipeline_id": str(pipeline.id),
        "job_id": str(pipeline.job_id) if pipeline.job_id else None,
        "previous_stage": previous_stage,
        "new_stage": new_stage,
        "stage_history_id": str(stage_history_id),
    }

    candidate_ref: dict[str, UUID] | None = None
    try:
        candidate_ref = CandidateManagementService(db).record_system_interaction(
            candidate_id=pipeline.candidate_id,
            interaction_type=InteractionType.STAGE_CHANGE,
            title=f"Pipeline stage: {new_stage}",
            body=note,
            interaction_metadata=stage_metadata,
            actor_user_id=actor_user_id,
        )
    except Exception:
        logger.warning(
            "comm_005.notify_stage_change failed pipeline_id=%s — suppressed",
            pipeline.id,
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            pass

    if candidate_ref is None or actor_user_id is None:
        return

    try:
        dispatch_task(
            task=None,
            fallback=run_pipeline_stage_email_notification,
            kwargs={
                "organization_id": str(organization_id),
                "org_id": str(candidate_ref["org_id"]),
                "workspace_id": str(candidate_ref["workspace_id"]),
                "candidate_id": str(pipeline.candidate_id),
                "pipeline_id": str(pipeline.id),
                "job_id": str(pipeline.job_id) if pipeline.job_id else None,
                "previous_stage": previous_stage,
                "new_stage": new_stage,
                "stage_history_id": str(stage_history_id),
                "actor_user_id": str(actor_user_id),
                "reason": reason,
            },
        )
    except Exception:
        logger.warning(
            "pipeline_stage_email.dispatch_failed pipeline_id=%s — suppressed",
            pipeline.id,
            exc_info=True,
        )


def _notify_status_change(
    *,
    db: Session,
    pipeline: Pipeline,
    previous_status: str,
    new_status: str,
    actor_user_id: UUID | None,
    reason: str | None,
) -> None:
    """
    COMM-005: Fire a best-effort notification on pipeline status change (PIPE-003).

    Records a CandidateInteraction for the status event via
    CandidateManagementService (which owns the write — see
    CandidateManagementService.record_system_interaction). Email / push
    delivery can be wired in here once COMM templates are defined for
    status events.
    """
    try:
        from app.candidate_management.models import InteractionType  # noqa: PLC0415
        from app.candidate_management.service import CandidateManagementService  # noqa: PLC0415

        note = f"Status changed: {previous_status} → {new_status}"
        if reason:
            note += f"\nReason: {reason}"

        CandidateManagementService(db).record_system_interaction(
            candidate_id=pipeline.candidate_id,
            interaction_type=InteractionType.STAGE_CHANGE,
            title=f"Pipeline status: {new_status}",
            body=note,
            actor_user_id=actor_user_id,
        )
    except Exception:
        logger.warning(
            "comm_005.notify_status_change failed pipeline_id=%s — suppressed",
            pipeline.id,
            exc_info=True,
        )
