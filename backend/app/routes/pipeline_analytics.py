"""PIPE-007: Pipeline Analytics routes.

GET  /api/v1/pipeline-analytics        — full analytics JSON response
GET  /api/v1/pipeline-analytics/export — CSV download
"""
from __future__ import annotations

import csv
import io
from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import PIPELINE_READ
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.pipeline_analytics import PipelineAnalyticsResponse
from app.services.pipeline_analytics_service import PipelineAnalyticsService

router = APIRouter(prefix="/pipeline-analytics", tags=["pipeline-analytics"])

_CSV_COLUMNS = [
    "section",
    "stage",
    "entered",
    "advanced",
    "rejected",
    "still_in_stage",
    "conversion_rate_pct",
    "rejection_rate_pct",
    "avg_days_in_stage",
    "median_days_in_stage",
    "sample_count",
    "drop_off_rank",
    "is_bottleneck",
]


@router.get(
    "",
    response_model=PipelineAnalyticsResponse,
    summary="Pipeline analytics: conversion rates, stage duration, drop-off (PIPE-007)",
)
def get_pipeline_analytics(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    job_id: Annotated[UUID | None, Query(description="Filter to a single job.")] = None,
    start_date: Annotated[
        date | None, Query(description="Inclusive start date (YYYY-MM-DD).")
    ] = None,
    end_date: Annotated[
        date | None, Query(description="Inclusive end date (YYYY-MM-DD).")
    ] = None,
) -> PipelineAnalyticsResponse:
    """
    GET /api/v1/pipeline-analytics — PIPE-007

    Returns:
    - **funnel**: stage-by-stage conversion rates (% advancing, % rejected)
    - **stage_durations**: average + median calendar days spent per stage
    - **drop_off**: per-stage rejection counts/rates ranked by severity (bottleneck flag)
    - **summary**: total pipelines, placed, rejected, overall placement rate

    Filters: `job_id` for per-job view; omit for cross-job org-wide view.
    Date range applied to both pipeline creation AND stage transition timestamps.

    Org-scoped: results are constrained to the authenticated user's organization.
    Vendor/client users additionally see only their allowed job set.
    """
    service = PipelineAnalyticsService(db)
    return service.get_analytics(
        UUID(current_user.organization_id),
        current_user,
        job_id=job_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get(
    "/export",
    summary="Export pipeline analytics as CSV (PIPE-007)",
    response_class=Response,
)
def export_pipeline_analytics_csv(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    job_id: Annotated[UUID | None, Query(description="Filter to a single job.")] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> Response:
    """
    GET /api/v1/pipeline-analytics/export — PIPE-007

    Returns a UTF-8 CSV file containing conversion funnel, drop-off data, and
    a summary row.  All org scoping / date range / job_id filters are respected.
    """
    service = PipelineAnalyticsService(db)
    rows = service.get_analytics_csv_rows(
        UUID(current_user.organization_id),
        current_user,
        job_id=job_id,
        start_date=start_date,
        end_date=end_date,
    )

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)

    # Build a descriptive filename that includes the filters used.
    parts = ["pipeline_analytics"]
    if job_id:
        parts.append(f"job_{str(job_id)[:8]}")
    if start_date:
        parts.append(f"from_{start_date}")
    if end_date:
        parts.append(f"to_{end_date}")
    filename = "_".join(parts) + ".csv"

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Generated-For-Org": current_user.organization_id,
        },
    )
