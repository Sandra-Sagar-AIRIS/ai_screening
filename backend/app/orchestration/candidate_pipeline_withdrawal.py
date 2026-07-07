"""Orchestrates Candidate -> Pipeline withdrawal (AIR-512).

Withdrawing a candidate's active pipelines when the candidate is archived
used to be a free function (app/services/candidate_pipeline_withdrawal.py,
since removed) that mutated Pipeline/PipelineStatusHistory directly from
the Candidate domain — no validation, no PIPE-003 audit trail, and no
notification. That function existed specifically to avoid a service-level
import cycle (CandidateService <-> PipelineService already import each
other). This module is the proper fix: it sits above both domains, so it
can call PipelineService.change_pipeline_status (the only method allowed to
mutate pipeline.status) without either service importing the other.

Both existing callers (CandidateService.archive_candidate and
candidate_management's _apply_soft_delete) already wrap this in their own
final `db.commit()`, so `commit=False` is used here to flush the status
change into that same transaction rather than committing independently —
this preserves the original all-or-nothing atomicity between the candidate
archive and the pipeline withdrawals.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pipeline import Pipeline
from app.schemas.auth import CurrentUser
from app.schemas.pipeline import PipelineStatus, PipelineStatusChangeRequest
from app.services.pipeline_service import PipelineService

_ACTIVE_PIPELINE_STATUSES = (
    PipelineStatus.ACTIVE.value,
    PipelineStatus.ON_HOLD.value,
)


def withdraw_active_pipelines_for_candidate(
    db: Session,
    *,
    candidate_id: UUID,
    organization_id: UUID,
    current_user: CurrentUser,
    reason: str = "Candidate removed",
) -> int:
    """Set active/on_hold pipelines to withdrawn when a candidate is archived.

    Routes each pipeline through PipelineService.change_pipeline_status, so
    the PIPE-003 validation (e.g. the closed-pipeline reopen guard) and
    PipelineStatusHistory audit trail apply here exactly as they do for any
    other status change — nothing about pipeline withdrawal is special-cased
    anymore.
    """
    pipelines = list(
        db.scalars(
            select(Pipeline).where(
                Pipeline.candidate_id == candidate_id,
                Pipeline.organization_id == organization_id,
                Pipeline.status.in_(_ACTIVE_PIPELINE_STATUSES),
            )
        )
    )
    pipeline_service = PipelineService(db)
    for pipeline in pipelines:
        pipeline_service.change_pipeline_status(
            pipeline.id,
            organization_id,
            current_user,
            PipelineStatusChangeRequest(status=PipelineStatus.WITHDRAWN, reason=reason),
            commit=False,
        )
    return len(pipelines)
