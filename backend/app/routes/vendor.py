from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import JOBS_READ_LIMITED
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.job import JobResponse, JobStatus
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

