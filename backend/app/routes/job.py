from __future__ import annotations

import io
import json
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import JOBS_CREATE, JOBS_READ, JOBS_UPDATE
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.job import (
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
)
from app.services.job_service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


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
    return service.list_jobs(
        UUID(current_user.organization_id),
        current_user,
        limit=limit,
        offset=offset,
        status=status_filter,
        client_id=client_id,
    )


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

async def _call_groq(text: str, api_key: str) -> dict:
    """Call Groq's OpenAI-compatible REST API and return the parsed JSON dict."""
    prompt = f"""Extract job details from this job description.
Return ONLY valid JSON with these exact fields:
{{
  "title": string,
  "location": string or null,
  "employment_type": "full_time" | "part_time" | "contract" | "internship" | null,
  "experience_min_years": integer or null,
  "experience_max_years": integer or null,
  "salary_min": integer or null,
  "salary_max": integer or null,
  "salary_currency": string default "USD",
  "urgency": "normal" | "high" | "critical",
  "description": string,
  "required_skills": [array of strings],
  "preferred_skills": [array of strings]
}}
No explanation. Only JSON.

JD TEXT:
{text}"""

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 1000,
            },
            timeout=30.0,
        )
        response.raise_for_status()

    result = response.json()
    content = result["choices"][0]["message"]["content"]
    # Strip markdown fences if the model wraps its output
    clean = content.replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


@router.post("/parse-jd", response_model=JobParseResponse)
async def parse_job_description(
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_CREATE))],
    pdf_file: Annotated[UploadFile | None, File()] = None,
    raw_text: Annotated[str | None, Form()] = None,
) -> JobParseResponse:
    """Parse a job description via PDF upload or pasted text using Groq AI (llama-3.3-70b)."""
    import pdfplumber  # already in requirements.txt

    settings = get_settings()
    api_key = settings.groq_api_key
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GROQ_API_KEY is not configured on the server.",
        )

    # ── Extract text ────────────────────────────────────────────────────────
    text = ""
    if pdf_file is not None:
        if not (pdf_file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only .pdf files are accepted.",
            )
        file_bytes = await pdf_file.read()
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages).strip()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read PDF: {exc}",
            ) from exc
    elif raw_text:
        text = raw_text.strip()

    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either a PDF file or raw_text.",
        )

    # ── Call Groq ────────────────────────────────────────────────────────────
    try:
        parsed = await _call_groq(text, api_key)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Groq returned malformed JSON — try again.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Groq API error: {exc.response.status_code}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Groq request failed: {exc}",
        ) from exc

    # ── Return only known fields (ignore any extra keys Groq may add) ────────
    return JobParseResponse(**{k: parsed.get(k) for k in JobParseResponse.model_fields})


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
    return service.change_job_status(
        job_id=job_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        new_status=payload.status,
    )


@router.post("/{job_id}/submit", response_model=JobSubmissionResponse, status_code=status.HTTP_201_CREATED)
def submit_candidate_to_job(
    job_id: UUID,
    payload: JobSubmissionCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobSubmissionResponse:
    service = JobService(db)
    submission = service.submit_candidate_to_job(
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
    _: Annotated[CurrentUser, Depends(require_permission(JOBS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobMatchesResponse:
    service = JobService(db)
    return service.get_matches(
        job_id=job_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        limit=limit,
        offset=offset,
    )
