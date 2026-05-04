from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import JOBS_CREATE, JOBS_READ, JOBS_UPDATE, SUBMISSIONS_CREATE
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.job import JobCreate, JobResponse, JobStatus, JobUpdate
from app.schemas.candidate import CandidateCreate, CandidateResponse
from app.models.job_vendor import JobVendor
from app.models.job import Job
from app.models.pipeline import Pipeline
from app.models.profile import Profile
from sqlalchemy.exc import IntegrityError
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobVendorAssignRequest(BaseModel):
    vendor_id: UUID


@router.post("/{job_id}/vendors", status_code=status.HTTP_201_CREATED)
def assign_vendor_to_job(
    job_id: UUID,
    payload: JobVendorAssignRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, str]:
    # Vendors should never be able to manage assignments that would grant them indirect access.
    if (current_user.role or "").strip().lower() == "vendor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: vendor cannot assign vendors.")

    org_id = UUID(current_user.organization_id)

    job = db.scalar(select(Job).where(Job.id == job_id, Job.organization_id == org_id))
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    vendor_id = payload.vendor_id
    vendor_profile = db.scalar(
        select(Profile).where(
            Profile.id == vendor_id,
            Profile.organization_id == org_id,
        )
    )
    if vendor_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vendor user not found.")
    if (vendor_profile.role or "").strip().lower() != "vendor":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="vendor_id must be a vendor user.")

    try:
        db.add(JobVendor(job_id=job_id, vendor_id=vendor_id))
        db.commit()
    except IntegrityError:
        db.rollback()

    return {"job_id": str(job_id), "vendor_id": str(vendor_id)}


@router.post("/{job_id}/candidates", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def vendor_submit_candidate(
    job_id: UUID,
    payload: CandidateCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(SUBMISSIONS_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CandidateResponse:
    # 1) Ensure caller is a vendor.
    if (current_user.role or "").strip().lower() != "vendor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: only vendors can submit candidates via this endpoint.")

    org_id = UUID(current_user.organization_id)
    user_id = UUID(current_user.user_id)

    # 2) Validate job exists and belongs to the caller's organization.
    job_exists = db.scalar(
        select(1).where(
            Job.id == job_id,
            Job.organization_id == org_id,
        )
    )
    if job_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    # 3) Critical authorization check: vendor must be assigned to this job.
    is_assigned = db.scalar(
        select(1).where(
            JobVendor.job_id == job_id,
            JobVendor.vendor_id == user_id,
        )
    )
    if is_assigned is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vendor not assigned to this job")

    # Use a single DB transaction so candidate + submission pipeline are atomic.
    try:
        with db.begin():
            # Keep candidate creation rules in service layer (single source of truth).
            candidate = CandidateService(db).create_candidate(
                org_id,
                payload,
                current_user=current_user,
                auto_commit=False,
            )

            db.add(
                Pipeline(
                    organization_id=org_id,
                    candidate_id=candidate.id,
                    job_id=job_id,
                    stage="applied",
                    status="active",
                    notes=None,
                )
            )
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pipeline already exists for this candidate and job.",
        ) from None

    return CandidateResponse.model_validate(candidate)


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobResponse:
    service = JobService(db)
    job = service.create_job(UUID(current_user.organization_id), payload)
    return JobResponse.model_validate(job)


@router.get("", response_model=list[JobResponse])
def list_jobs(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    client_id: Annotated[UUID | None, Query()] = None,
) -> list[JobResponse]:
    service = JobService(db)
    jobs = service.list_jobs(
        UUID(current_user.organization_id),
        current_user,
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
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobResponse:
    service = JobService(db)
    job = service.get_job_by_id(job_id, UUID(current_user.organization_id), current_user)
    return JobResponse.model_validate(job)


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: UUID,
    payload: JobUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobResponse:
    service = JobService(db)
    job = service.update_job(
        job_id=job_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return JobResponse.model_validate(job)
