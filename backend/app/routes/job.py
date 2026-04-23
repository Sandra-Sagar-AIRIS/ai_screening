from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_recruiter_or_admin
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.job import JobCreate, JobResponse, JobStatus, JobUpdate
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_recruiter_or_admin)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobResponse:
    service = JobService(db)
    job = service.create_job(UUID(current_user.organization_id), payload)
    return JobResponse.model_validate(job)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    client_id: Annotated[UUID | None, Query()] = None,
) -> list[JobResponse]:
    service = JobService(db)
    jobs = service.list_jobs(
        UUID(current_user.organization_id),
        limit=limit,
        offset=offset,
        status=status_filter,
        client_id=client_id,
    )
    return [JobResponse.model_validate(job) for job in jobs]


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobResponse:
    service = JobService(db)
    job = service.get_job_by_id(job_id, UUID(current_user.organization_id))
    return JobResponse.model_validate(job)


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: UUID,
    payload: JobUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_recruiter_or_admin)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobResponse:
    service = JobService(db)
    job = service.update_job(
        job_id=job_id,
        organization_id=UUID(current_user.organization_id),
        payload=payload,
    )
    return JobResponse.model_validate(job)
