from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.pipeline import Pipeline
from app.core.config import get_settings
from app.schemas.auth import CurrentUser
from app.schemas.pipeline import PipelineCreate, PipelineStage, PipelineStatus, PipelineUpdate
from app.services.access_scope_service import AccessScopeService
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService

logger = logging.getLogger(__name__)


class PipelineService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._scope = AccessScopeService(db)
        self._candidates = CandidateService(db)
        self._jobs = JobService(db)

    def create_pipeline(self, organization_id: UUID, current_user: CurrentUser, payload: PipelineCreate) -> Pipeline:
        self._candidates.get_candidate_by_id(payload.candidate_id, organization_id, current_user)
        self._jobs.get_job_by_id(payload.job_id, organization_id, current_user)

        existing = self.db.scalar(
            select(Pipeline.id).where(
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
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A pipeline already exists for this candidate and job.",
            ) from None
        self.db.refresh(pipeline)
        return pipeline

    def list_pipelines(
        self,
        organization_id: UUID,
        current_user: CurrentUser,
        *,
        limit: int = 50,
        offset: int = 0,
        job_id: UUID | None = None,
        stage: PipelineStage | None = None,
    ) -> list[Pipeline]:
        stmt: Select[tuple[Pipeline]] = select(Pipeline).where(Pipeline.organization_id == organization_id)
        if job_id is not None:
            stmt = stmt.where(Pipeline.job_id == job_id)
        if stage is not None:
            stmt = stmt.where(Pipeline.stage == stage.value)
        if self._scope.is_scoped_user(current_user):
            stmt = stmt.where(Pipeline.job_id.in_(self._scope.allowed_job_ids_subquery(current_user)))
        stmt = stmt.order_by(Pipeline.created_at.desc()).offset(offset).limit(limit)
        return list(self.db.scalars(stmt))

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
