"""Orchestrates Pipeline stage transitions -> PlacementHistory.

PipelineService.transition_stage used to call PlacementHistoryService
directly and commit both writes together. It no longer does either — see
app/services/pipeline_service.py. This module is now the one place that
knows a stage transition also needs a PlacementHistory record, and is
responsible for the flush/commit choreography between the two domains
(mirrors app.orchestration.job_submission's Job -> Pipeline pattern).

Every real caller of PipelineService.transition_stage (the pipeline stage
route, OfferService's auto-transitions, and the AI-screening orchestrator)
goes through this function now, so PlacementHistory keeps getting recorded
for every stage change exactly as before.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pipeline import Pipeline, PipelineStageHistory
from app.schemas.auth import CurrentUser
from app.schemas.pipeline import PipelineStageTransitionRequest
from app.services.pipeline_service import PipelineService
from app.services.placement_history_service import PlacementHistoryService


def transition_pipeline_stage(
    db: Session,
    pipeline_id: UUID,
    organization_id: UUID,
    current_user: CurrentUser,
    payload: PipelineStageTransitionRequest,
) -> Pipeline:
    pipeline_service = PipelineService(db)

    # Capture the pre-transition stage for the post-commit notification —
    # transition_stage mutates pipeline.stage in place, so this has to be
    # read before calling it.
    previous_stage = pipeline_service.get_pipeline_by_id(pipeline_id, organization_id, current_user).stage

    pipeline = pipeline_service.transition_stage(
        pipeline_id,
        organization_id,
        current_user,
        payload,
        commit=False,
    )
    new_stage = pipeline.stage

    PlacementHistoryService(db).record_pipeline_stage(
        candidate_id=pipeline.candidate_id,
        job_id=pipeline.job_id,
        stage=new_stage,
        transitioned_at=pipeline.stage_updated_at,
    )

    # Commit the stage change, its PipelineStageHistory row, and the
    # PlacementHistory record together — matches the original atomicity of
    # transition_stage's internal (now-removed) PlacementHistoryService call.
    db.commit()
    db.refresh(pipeline)

    stage_history_id = db.scalar(
        select(PipelineStageHistory.id)
        .where(PipelineStageHistory.pipeline_id == pipeline.id)
        .order_by(PipelineStageHistory.transitioned_at.desc())
        .limit(1)
    )
    pipeline_service.run_post_transition_side_effects(
        pipeline,
        organization_id=organization_id,
        current_user=current_user,
        previous_stage=previous_stage,
        new_stage=new_stage,
        reason=payload.reason,
        stage_history_id=stage_history_id,
    )
    return pipeline
