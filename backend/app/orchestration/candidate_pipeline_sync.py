"""Orchestrates Candidate -> Pipeline stage synchronization (AIRIS Phase 0.5 Task A1).

candidate_management._sync_candidate_pipeline used to construct and mutate
Pipeline ORM objects directly (including `pipeline.stage = mapped_stage`
with no validation, no PipelineStageHistory row, and no PlacementHistory
record). This module replaces that direct write: the Candidate domain now
only reads its own Candidate row and calls
PipelineService.sync_stage_for_candidate, which is the only method allowed
to create or mutate a Pipeline row for a system-driven change.

This is a thin pass-through, not a multi-domain transaction coordinator —
unlike job_submission.py or pipeline_transitions.py, there's nothing to
combine into one commit here, so PipelineService.sync_stage_for_candidate
manages its own commit.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.candidate_management.models import Candidate
from app.candidate_management.service import CandidateManagementService
from app.models.pipeline import Pipeline
from app.services.pipeline_service import PipelineService


def sync_pipeline_stage_for_candidate(
    db: Session,
    *,
    candidate: Candidate,
    actor_user_id: UUID | None,
) -> Pipeline | None:
    """Sync the candidate's pipeline to reflect their current stage.

    No-ops if the candidate isn't associated with a job (matches the prior
    _sync_candidate_pipeline behavior — nothing to sync without a job_id).
    """
    if candidate.job_id is None:
        return None

    new_stage = CandidateManagementService._candidate_stage_to_pipeline_stage(candidate.stage)

    return PipelineService(db).sync_stage_for_candidate(
        organization_id=candidate.org_id,
        candidate_id=candidate.id,
        job_id=candidate.job_id,
        new_stage=new_stage,
        actor_user_id=actor_user_id,
        reason=(
            f"System sync: candidate stage updated to '{candidate.stage}' "
            f"(candidate management sync{f' by {actor_user_id}' if actor_user_id else ''})"
        ),
    )
