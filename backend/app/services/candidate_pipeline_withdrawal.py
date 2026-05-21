"""AIR-512: Withdraw active pipelines when a candidate is soft-deleted (no service cycles)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.pipeline import Pipeline, PipelineStatusHistory
from app.schemas.pipeline import PipelineStatus

_ACTIVE_PIPELINE_STATUSES = (
    PipelineStatus.ACTIVE.value,
    PipelineStatus.ON_HOLD.value,
)


def withdraw_active_pipelines_for_candidate(
    db: Session,
    *,
    candidate_id: UUID,
    organization_id: UUID,
    actor_user_id: UUID | None,
    reason: str = "Candidate removed",
) -> int:
    """Set active/on_hold pipelines to withdrawn when a candidate is soft-deleted."""
    now = datetime.now(UTC)
    pipelines = list(
        db.scalars(
            select(Pipeline).where(
                Pipeline.candidate_id == candidate_id,
                Pipeline.organization_id == organization_id,
                Pipeline.status.in_(_ACTIVE_PIPELINE_STATUSES),
            )
        )
    )
    for pipeline in pipelines:
        previous = pipeline.status
        db.add(
            PipelineStatusHistory(
                pipeline_id=pipeline.id,
                organization_id=organization_id,
                previous_status=previous,
                new_status=PipelineStatus.WITHDRAWN.value,
                actor_user_id=actor_user_id,
                reason=reason,
                changed_at=now,
            )
        )
        pipeline.status = PipelineStatus.WITHDRAWN.value
        pipeline.status_changed_at = now
        db.add(pipeline)
    if pipelines:
        db.flush()
    return len(pipelines)
