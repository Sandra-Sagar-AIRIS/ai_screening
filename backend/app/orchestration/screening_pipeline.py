"""Orchestrates AI Screening <-> Pipeline stage transitions (both directions).

AIScreeningService no longer imports or mutates the Pipeline model (see
app/services/ai_screening_service.py — advance_pipeline_from_screening was
removed from that class). Moving a candidate's pipeline after a recruiter
reviews an AI screening now goes through
app.orchestration.pipeline_transitions.transition_pipeline_stage — the same
orchestration entry point used by the pipeline-stage route and OfferService
— so the same VALID_TRANSITIONS validation and PipelineStageHistory /
PlacementHistory audit trail applied to every other stage change also
applies here. Nothing about an AI-screening-triggered transition is
special-cased anymore.

The reverse direction (PipelineService.transition_stage auto-creating a
screening when a pipeline enters the ai_interview stage) is
auto_create_screening_for_pipeline below — PipelineService no longer
imports or instantiates AIScreeningService directly either (AIRIS Phase 0.5,
final Pipeline<->Screening cleanup).
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pipeline import Pipeline
from app.orchestration.pipeline_transitions import transition_pipeline_stage
from app.schemas.auth import CurrentUser
from app.schemas.pipeline import PipelineStage, PipelineStageTransitionRequest, PipelineUpdate

logger = logging.getLogger(__name__)

# transition_stage requires >=10 chars when rejecting (see
# PipelineStageTransitionRequest.validate_rejection_reason) — the old
# advance_pipeline_from_screening had no reason field at all, so this
# fallback guarantees the transition never fails validation purely for
# lacking one, while still surfacing the recruiter's own notes when present.
_DEFAULT_REJECT_REASON = "AI screening review — recruiter rejected candidate after screening review."


def advance_pipeline_from_screening(
    db: Session,
    *,
    organization_id: UUID,
    candidate_id: UUID,
    job_id: UUID,
    recommendation: str,
    current_user: CurrentUser,
    notes: str | None = None,
) -> None:
    """Move the candidate's pipeline entry after a recruiter reviews an AI screening.

    recommendation values accepted:
      "advance" | anything except "reject"  -> interview stage
      "reject"                               -> rejected

    No-ops (matching the previous behavior) if no pipeline is currently in
    the ai_interview stage for this candidate/job.
    """
    pipeline = db.scalar(
        select(Pipeline).where(
            Pipeline.organization_id == organization_id,
            Pipeline.candidate_id == candidate_id,
            Pipeline.job_id == job_id,
            Pipeline.stage == PipelineStage.AI_INTERVIEW.value,
        )
    )
    if not pipeline:
        logger.warning("ai_screening.advance.not_found candidate=%s", candidate_id)
        return

    if recommendation == "reject":
        new_stage = PipelineStage.REJECTED
        reason = f"{_DEFAULT_REJECT_REASON} Recruiter notes: {notes.strip()}" if notes and notes.strip() \
            else _DEFAULT_REJECT_REASON
    else:
        new_stage = PipelineStage.INTERVIEW
        reason = None

    transition_pipeline_stage(
        db,
        pipeline.id,
        organization_id,
        current_user,
        PipelineStageTransitionRequest(stage=new_stage, reason=reason),
    )
    logger.info("ai_screening.pipeline_advanced candidate=%s ->%s", candidate_id, new_stage.value)


def set_pipeline_stage_from_screening(
    db: Session,
    *,
    pipeline_id: UUID,
    organization_id: UUID,
    current_user: CurrentUser,
    stage: PipelineStage,
) -> Pipeline:
    """Directly set a pipeline's stage from the AI Screening domain.

    Used by AIScreeningService.start_screening (moving a pipeline to the
    ai_interview stage when a screening is created) and .move_pipeline_stage
    (an arbitrary recruiter-driven stage set from the screening review
    panel) — both call sites previously imported PipelineService directly
    from app/routes/ai_screening.py.

    Unlike advance_pipeline_from_screening, this is an unrestricted setter —
    it does not validate against PIPE-002's VALID_TRANSITIONS — because it
    goes through PipelineService.update_pipeline, exactly as both original
    route call sites did. Preserved as-is rather than upgraded to
    transition_pipeline_stage, to avoid changing behavior beyond relocating
    where the Pipeline domain is called from.
    """
    from app.services.pipeline_service import PipelineService  # noqa: PLC0415

    return PipelineService(db).update_pipeline(
        pipeline_id,
        organization_id,
        current_user,
        PipelineUpdate(stage=stage),
    )


def auto_create_screening_for_pipeline(
    db: Session,
    *,
    organization_id: UUID,
    candidate_id: UUID,
    job_id: UUID,
    pipeline_id: UUID,
    created_by: UUID | None,
) -> None:
    """Auto-create a live AI screening when a pipeline enters the ai_interview stage.

    Used by PipelineService.transition_stage, which previously imported and
    instantiated AIScreeningService directly. Idempotent — see
    AIScreeningService.auto_create_for_pipeline, which no-ops if a live
    screening already exists for this candidate/job.
    """
    from app.services.ai_screening_service import AIScreeningService  # noqa: PLC0415

    AIScreeningService(db).auto_create_for_pipeline(
        org_id=organization_id,
        candidate_id=candidate_id,
        job_id=job_id,
        pipeline_id=pipeline_id,
        created_by=created_by,
    )
