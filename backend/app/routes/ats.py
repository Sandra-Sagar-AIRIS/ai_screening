from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_any_permissions
from app.core.permissions import ATS_READ, ATS_RESCORE, JOBS_READ, CANDIDATES_READ, CANDIDATES_READ_OWN
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.job import AtsPairStatusResponse
from app.services.job_service import JobService

router = APIRouter(prefix="/ats", tags=["ats"])


@router.get("/status/{candidate_id}/{job_id}", response_model=AtsPairStatusResponse)
def get_ats_pair_status(
    candidate_id: UUID,
    job_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[
        CurrentUser,
        Depends(require_any_permissions(ATS_READ, ATS_RESCORE, JOBS_READ, CANDIDATES_READ, CANDIDATES_READ_OWN)),
    ],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AtsPairStatusResponse:
    service = JobService(db)
    return service.get_ats_pair_status(
        organization_id=UUID(current_user.organization_id),
        candidate_id=candidate_id,
        job_id=job_id,
    )

