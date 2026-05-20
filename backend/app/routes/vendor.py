from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_any_permissions, require_permission
from app.core.permissions import JOBS_READ_LIMITED, SUBMISSIONS_READ_OWN
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.job import JobResponse, JobStatus, VendorSubmissionResponse
from app.services.job_service import JobService

router = APIRouter(prefix="/vendor", tags=["vendor"])


@router.get("/jobs", response_model=list[JobResponse])
def list_vendor_jobs(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ_LIMITED))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
) -> list[JobResponse]:
    # Security enforcement:
    # This endpoint is intended only for vendor role users. Even if a non-vendor user
    # is (mis)granted `jobs:read_limited`, they should not be able to use the vendor
    # job-view path.
    if (current_user.role or "").strip().lower() != "vendor":
        raise HTTPException(status_code=403, detail="Forbidden: only vendors can access this endpoint.")

    service = JobService(db)
    jobs = service.list_jobs(
        UUID(current_user.organization_id),
        current_user,
        limit=limit,
        offset=offset,
        status=status_filter,
        client_id=None,
    )
    return [JobResponse.model_validate(job) for job in jobs]


@router.get(
    "/submissions",
    response_model=list[VendorSubmissionResponse],
    summary="List this vendor's own submissions across all jobs (PIPE-005)",
)
def list_vendor_submissions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(SUBMISSIONS_READ_OWN))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[VendorSubmissionResponse]:
    """
    GET /vendor/submissions — PIPE-005

    Returns only the calling vendor's own submissions.
    Cross-vendor isolation is enforced at the SQL level via vendor_id = current_user.user_id.
    Statuses visible: submitted | under_review | accepted | rejected.
    Client feedback is only surfaced when a final outcome has been set.
    """
    if (current_user.role or "").strip().lower() != "vendor":
        raise HTTPException(status_code=403, detail="Forbidden: only vendors can access this endpoint.")

    service = JobService(db)
    return service.list_vendor_submissions(
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        limit=limit,
        offset=offset,
    )

