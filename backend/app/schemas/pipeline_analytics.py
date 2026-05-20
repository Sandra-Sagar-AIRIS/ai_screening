"""PIPE-007: Pipeline Analytics schemas."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class StageFunnelEntry(BaseModel):
    """Conversion funnel data for one stage."""

    stage: str
    label: str
    entered: int = Field(..., description="Distinct pipelines that entered this stage.")
    advanced: int = Field(..., description="Pipelines that advanced to the next forward stage.")
    rejected: int = Field(..., description="Pipelines rejected directly from this stage.")
    still_in_stage: int = Field(..., description="Pipelines currently sitting in this stage.")
    conversion_rate: float = Field(
        ...,
        description="Percentage of entered that advanced (0-100).",
    )
    rejection_rate: float = Field(
        ...,
        description="Percentage of entered that were rejected directly (0-100).",
    )


class StageDurationEntry(BaseModel):
    """Average / median time spent in a stage."""

    stage: str
    label: str
    avg_days: float = Field(..., description="Average calendar days spent in this stage.")
    median_days: float | None = Field(None, description="Median days (P50) when available.")
    sample_count: int = Field(..., description="Number of completed stage observations used.")
    is_slow: bool = Field(
        False,
        description="True when avg_days is above the global mean across all stages.",
    )


class DropOffEntry(BaseModel):
    """Drop-off (rejection) statistics per stage."""

    stage: str
    label: str
    rejected_count: int
    drop_off_rate: float = Field(..., description="Rejected / entered × 100.")
    is_bottleneck: bool = Field(
        False,
        description="True for the stage with the highest drop-off rate.",
    )
    rank: int = Field(..., description="1 = highest drop-off.")


class PipelineAnalyticsResponse(BaseModel):
    """PIPE-007: Full analytics payload for the dashboard."""

    organization_id: UUID
    job_id: UUID | None = None
    date_range_start: date | None = None
    date_range_end: date | None = None

    total_pipelines: int = Field(..., description="Total pipelines matching the filters.")
    total_placed: int = Field(..., description="Candidates successfully placed.")
    total_rejected: int = Field(..., description="Candidates rejected at any stage.")
    overall_placement_rate: float = Field(
        ..., description="Placed / (Placed + Rejected) × 100."
    )

    funnel: list[StageFunnelEntry] = Field(
        default_factory=list,
        description="Ordered funnel from applied → placed.",
    )
    stage_durations: list[StageDurationEntry] = Field(
        default_factory=list,
        description="Avg days per stage (completed transitions only).",
    )
    drop_off: list[DropOffEntry] = Field(
        default_factory=list,
        description="Per-stage drop-off rates, ranked by severity.",
    )

    generated_at: datetime
