from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.dependencies import get_current_user, require_any_permissions, require_permission
from app.core.permissions import (
    ATS_READ,
    ATS_RESCORE,
    CANDIDATES_READ,
    CANDIDATES_READ_OWN,
    JOBS_CREATE,
    JOBS_READ,
    JOBS_UPDATE,
    PIPELINE_READ,
    SUBMISSIONS_CREATE,
    SUBMISSIONS_READ_OWN,
)
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.job import (
    ClientFeedbackUpdate,
    JobCreate,
    JobParseResponse,
    JobResponse,
    JobStatus,
    JobStatusTransition,
    JobSubmissionCreate,
    JobSubmissionResponse,
    JobSubmissionStatus,
    JobSubmissionStatusUpdate,
    JobMatchTriggerRequest,
    JobMatchTriggerResponse,
    JobMatchesResponse,
    JobUpdate,
    SubmissionOutcomeUpdate,
)
from app.schemas.candidate import CandidateCreate, CandidateResponse
from app.schemas.job_dedup import DuplicateJobCheckRequest, DuplicateJobCheckResult, DuplicateJobMatchOut
from app.services.job_dedup.detection_service import DuplicateJobDetectionService
from app.orchestration import job_submission
from app.services.job_service import JobService
from app.services.pipeline_service import PipelineService

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)


class JobVendorAssignRequest(BaseModel):
    vendor_id: UUID


class JobVendorItem(BaseModel):
    vendor_id: UUID
    email: str


class JobPipelineCandidateItem(BaseModel):
    """Candidate rows for a job via application pipeline (one entry per pipeline row)."""

    pipeline_id: UUID
    id: UUID
    first_name: str
    last_name: str
    email: str
    source_type: str


class JobMetricsItem(BaseModel):
    job_id: UUID
    vendor_count: int
    candidate_count: int


@router.get("/{job_id}/candidates", response_model=list[JobPipelineCandidateItem])
def list_job_candidates(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    _cand_read: Annotated[CurrentUser, Depends(require_any_permissions(CANDIDATES_READ, CANDIDATES_READ_OWN))],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JobPipelineCandidateItem]:
    org_id = UUID(current_user.organization_id)
    job_service = JobService(db)
    job_service.get_job_by_id(job_id, org_id, current_user)

    rows = PipelineService(db).list_pipeline_candidates_for_job(
        job_id,
        org_id,
        current_user,
        limit=limit,
        offset=offset,
    )
    return [
        JobPipelineCandidateItem(
            pipeline_id=pid,
            id=candidate.id,
            first_name=candidate.first_name,
            last_name=candidate.last_name,
            email=candidate.email,
            source_type=candidate.source_type,
        )
        for pid, candidate in rows
    ]


@router.get("/{job_id}/vendors", response_model=list[JobVendorItem])
def list_job_vendors(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[JobVendorItem]:
    org_id = UUID(current_user.organization_id)
    rows = JobService(db).list_job_vendors(job_id, org_id, current_user)
    return [JobVendorItem(vendor_id=vendor_id, email=email) for vendor_id, email in rows]


@router.delete("/{job_id}/vendors/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_vendor_from_job(
    job_id: UUID,
    vendor_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Response:
    org_id = UUID(current_user.organization_id)
    JobService(db).remove_vendor(job_id, vendor_id, org_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{job_id}/vendors", status_code=status.HTTP_201_CREATED)
def assign_vendor_to_job(
    job_id: UUID,
    payload: JobVendorAssignRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, str]:
    org_id = UUID(current_user.organization_id)
    JobService(db).assign_vendor(job_id, payload.vendor_id, org_id, current_user)
    return {"job_id": str(job_id), "vendor_id": str(payload.vendor_id)}


@router.get("/metrics", response_model=list[JobMetricsItem])
def get_jobs_metrics(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[JobMetricsItem]:
    org_id = UUID(current_user.organization_id)
    rows = JobService(db).get_jobs_metrics(org_id, current_user)
    return [JobMetricsItem(**row) for row in rows]


@router.post("/{job_id}/candidates", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def vendor_submit_candidate(
    job_id: UUID,
    payload: CandidateCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(SUBMISSIONS_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CandidateResponse:
    org_id = UUID(current_user.organization_id)
    candidate = job_submission.vendor_submit_candidate(
        db,
        job_id=job_id,
        organization_id=org_id,
        current_user=current_user,
        payload=payload,
    )

    return CandidateResponse.model_validate(candidate)


@router.post("/check-duplicate", response_model=DuplicateJobCheckResult)
def check_duplicate(
    payload: DuplicateJobCheckRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> DuplicateJobCheckResult:
    org_id = UUID(current_user.organization_id)
    
    client_id = payload.client_id
    if not client_id:
        from app.services.job_service import JobService
        job_svc = JobService(db)
        default_client = job_svc.get_or_create_default_client(org_id)
        if default_client:
            client_id = default_client.id

    svc = DuplicateJobDetectionService()
    result = svc.check(
        title=payload.title,
        client_id=client_id,
        location=payload.location,
        org_id=org_id,
        db=db,
        exclude_id=payload.exclude_id,
    )
    return DuplicateJobCheckResult(
        has_duplicates=result.has_duplicates,
        matches=[
            DuplicateJobMatchOut(
                job_id=m.job_id,
                title=m.title,
                status=m.status,
                created_at=m.created_at,
                client_id=m.client_id,
                location=m.location,
                confidence=m.confidence,
            )
            for m in result.matches
        ],
    )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    payload: JobCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobResponse:
    service = JobService(db)
    # The service returns a JobResponse (with embedded skills) directly
    return service.create_job(
        UUID(current_user.organization_id),
        payload,
        created_by=UUID(current_user.user_id),
    )


@router.post("/{job_id}/jd-document", response_model=JobResponse)
async def upload_job_jd_document(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> JobResponse:
    """Attach or replace the original JD file (PDF, DOC, DOCX, TXT)."""
    content = await file.read()
    service = JobService(db)
    return service.save_job_jd_upload(
        job_id,
        UUID(current_user.organization_id),
        current_user,
        content,
        file.filename or "job-description.pdf",
    )


@router.get("/{job_id}/jd-document")
def download_job_jd_document(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    disposition: Annotated[str, Query(pattern="^(inline|attachment)$")] = "attachment",
):
    """Serve the original JD with Content-Disposition inline (preview) or attachment (download)."""
    service = JobService(db)
    job = service.get_job_by_id(job_id, UUID(current_user.organization_id), current_user)
    path = service.jd_disk_path_for_job(job)
    if path is None or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No JD document stored for this job.")
    from app.documents.file_security import media_type_for_filename

    media_type = media_type_for_filename(job.jd_file_name or path.name)
    return FileResponse(
        path=str(path),
        filename=job.jd_file_name or path.name,
        media_type=media_type,
        content_disposition_type=disposition,
    )


@router.get("/{job_id}/jd-document/preview")
def preview_job_jd_document(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Return server-generated HTML preview for DOC/DOCX (same contract as resume preview)."""
    service = JobService(db)
    job = service.get_job_by_id(job_id, UUID(current_user.organization_id), current_user)
    path = service.jd_disk_path_for_job(job)
    if path is None or not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No JD document stored for this job.")

    name = (job.jd_file_name or path.name).lower()
    if name.endswith(".docx"):
        from app.documents.docx_html_preview import docx_body_html_from_path, wrap_document_preview_html

        body_html = docx_body_html_from_path(path)
        html_doc = wrap_document_preview_html(
            title="Job description preview",
            display_name=job.jd_file_name or path.name,
            body_html=body_html,
        )
    elif name.endswith(".doc"):
        body_html = (
            "<p>Preview for .doc is limited.</p>"
            "<p>Please use <strong>Download</strong> to view the original file in Word for full fidelity.</p>"
        )
        from app.documents.docx_html_preview import wrap_document_preview_html

        html_doc = wrap_document_preview_html(
            title="Job description preview",
            display_name=job.jd_file_name or path.name,
            body_html=body_html,
        )
    else:
        body_html = "<p>Inline server preview is available for DOCX. Use Open for PDF/TXT or Download for the original file.</p>"
        from app.documents.docx_html_preview import wrap_document_preview_html

        html_doc = wrap_document_preview_html(
            title="Job description preview",
            display_name=job.jd_file_name or path.name,
            body_html=body_html,
        )

    return {
        "file_name": job.jd_file_name or path.name,
        "html": html_doc,
    }


@router.get("", response_model=list[JobResponse])
def list_jobs(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    client_id: Annotated[UUID | None, Query()] = None,
) -> list[JobResponse]:
    service = JobService(db)
    try:
        return service.list_jobs(
            UUID(current_user.organization_id),
            current_user,
            limit=limit,
            offset=offset,
            status=status_filter,
            client_id=client_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("list_jobs.unhandled", extra={"org": current_user.organization_id})
        raise HTTPException(status_code=500, detail=str(exc) or "Failed to list jobs") from exc


# BUG FIX: Move /search ABOVE /{job_id} to avoid shadowing
@router.get("/search", response_model=list[JobResponse])
def search_jobs(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[JobStatus | None, Query(alias="status")] = None,
    urgency: Annotated[str | None, Query()] = None,
    location: Annotated[str | None, Query()] = None,
    skills: Annotated[str | None, Query()] = None,
    client_id: Annotated[UUID | None, Query()] = None,
    min_experience: Annotated[int | None, Query()] = None, # Task 6
    max_experience: Annotated[int | None, Query()] = None, # Task 6
    salary_min: Annotated[float | None, Query()] = None,   # Task 6
    salary_max: Annotated[float | None, Query()] = None,   # Task 6
    employment_type: Annotated[str | None, Query()] = None, # Task 6
) -> list[JobResponse]:
    service = JobService(db)
    skill_list = [s.strip() for s in (skills or "").split(",") if s.strip()] if skills else None
    return service.search_jobs(
        UUID(current_user.organization_id),
        current_user,
        limit=limit,
        offset=offset,
        status_filter=status,
        urgency=urgency,
        location=location,
        skills=skill_list,
        client_id=client_id,
        min_experience=min_experience,
        max_experience=max_experience,
        salary_min=salary_min,
        salary_max=salary_max,
        employment_type=employment_type,
    )


# ------------------------------------------------------------------
# AI-powered JD parser  (placed above /{job_id} to avoid shadowing)
# ------------------------------------------------------------------

@router.post("/parse-jd", response_model=JobParseResponse)
async def parse_job_description(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_CREATE))],
    pdf_file: Annotated[UploadFile | None, File()] = None,
    raw_text: Annotated[str | None, Form()] = None,
) -> JobParseResponse:
    """Parse a job description via file upload (.pdf/.doc/.docx) or pasted text.

    Reading the multipart UploadFile stays here (request-bound async I/O);
    format detection, text extraction, the LLM call, and response
    normalization all live in JobService.parse_job_description.
    """
    file_bytes: bytes | None = None
    filename: str | None = None
    if pdf_file is not None:
        filename = pdf_file.filename
        file_bytes = await pdf_file.read()

    return await JobService(db).parse_job_description(
        file_bytes=file_bytes,
        filename=filename,
        raw_text=raw_text,
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobResponse:
    service = JobService(db)
    return service.get_job_response_by_id(job_id, UUID(current_user.organization_id), current_user)


@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: UUID,
    payload: JobUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobResponse:
    service = JobService(db)
    return service.update_job(
        job_id=job_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
):
    service = JobService(db)
    service.delete_job(job_id, UUID(current_user.organization_id), current_user)
    return None


@router.patch("/{job_id}", response_model=JobResponse)
def patch_update_job(
    job_id: UUID,
    payload: JobUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobResponse:
    service = JobService(db)
    return service.update_job(
        job_id=job_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )


@router.patch("/{job_id}/status", response_model=JobResponse)
def patch_change_job_status(
    job_id: UUID,
    payload: JobStatusTransition,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobResponse:
    service = JobService(db)
    return service.update_job_status(
        job_id=job_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        new_status=payload.status,
        reason=payload.reason,
    )


@router.post("/{job_id}/submit", response_model=JobSubmissionResponse, status_code=status.HTTP_201_CREATED)
def submit_candidate_to_job(
    job_id: UUID,
    payload: JobSubmissionCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_any_permissions(JOBS_UPDATE, SUBMISSIONS_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobSubmissionResponse:
    submission = job_submission.submit_candidate_to_job(
        db,
        job_id=job_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return submission


@router.get(
    "/{job_id}/submissions",
)
def list_job_submissions(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    submission_status: Annotated[JobSubmissionStatus | None, Query(alias="submission_status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    service = JobService(db)
    items = service.list_job_submissions(
        job_id=job_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        submission_status=submission_status,
        limit=limit,
        offset=offset,
    )
    if not items:
        return {"data": [], "total": 0}
    return {"data": items, "total": len(items)}



@router.patch(
    "/{job_id}/submissions/{submission_id}",
    response_model=JobSubmissionResponse,
)
def update_job_submission_status(
    job_id: UUID,
    submission_id: UUID,
    payload: JobSubmissionStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobSubmissionResponse:
    """Task 7: Update submission status."""
    service = JobService(db)
    return service.update_submission_status(
        job_id=job_id,
        submission_id=submission_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )


@router.post(
    "/{job_id}/submissions/{submission_id}/outcome",
    response_model=JobSubmissionResponse,
    summary="Set submission outcome and client feedback (PIPE-005)",
)
def update_submission_outcome(
    job_id: UUID,
    submission_id: UUID,
    payload: SubmissionOutcomeUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobSubmissionResponse:
    """
    POST /jobs/{job_id}/submissions/{submission_id}/outcome — PIPE-005

    Set the client outcome (accepted/rejected/pending) and optional free-text feedback.
    Vendors cannot call this endpoint. Status update is reflected in real-time via vendor polling.
    """
    service = JobService(db)
    return service.update_submission_outcome(
        job_id=job_id,
        submission_id=submission_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )


@router.patch(
    "/{job_id}/submissions/{submission_id}/feedback",
    response_model=JobSubmissionResponse,
    summary="Update client feedback on a submission (PIPE-005)",
)
def update_submission_feedback(
    job_id: UUID,
    submission_id: UUID,
    payload: ClientFeedbackUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobSubmissionResponse:
    """
    PATCH /jobs/{job_id}/submissions/{submission_id}/feedback — PIPE-005

    Update client feedback text independently of outcome.
    """
    service = JobService(db)
    return service.update_client_feedback(
        job_id=job_id,
        submission_id=submission_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )


@router.post(
    "/{job_id}/match",
    response_model=JobMatchTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_job_matching(
    job_id: UUID,
    request: JobMatchTriggerRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobMatchTriggerResponse:
    service = JobService(db)
    return service.trigger_matching(
        job_id=job_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        request=request,
    )


@router.get(
    "/{job_id}/matches",
    response_model=JobMatchesResponse,
)
def get_job_matches(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_any_permissions(JOBS_READ, ATS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort_by: Annotated[str, Query()] = "score_desc",
    min_score: Annotated[int | None, Query(ge=0, le=100)] = None,
    recommendation: Annotated[str | None, Query()] = None,
) -> JobMatchesResponse:
    service = JobService(db)
    return service.get_matches(
        job_id=job_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        min_score=min_score,
        recommendation=recommendation,
    )


@router.post(
    "/{job_id}/rescore",
    response_model=JobMatchTriggerResponse,
)
def rescore_job_matches(
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_any_permissions(JOBS_UPDATE, ATS_RESCORE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobMatchTriggerResponse:
    org_id = UUID(current_user.organization_id)
    return JobService(db).rescore_and_report(organization_id=org_id, job_id=job_id, current_user=current_user)
