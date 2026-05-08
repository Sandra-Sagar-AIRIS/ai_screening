from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_any_permissions, require_permission
from app.core.permissions import ATS_READ, ATS_RESCORE, CANDIDATES_CREATE, CANDIDATES_READ, CANDIDATES_READ_OWN, CANDIDATES_UPDATE
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.candidate import CandidateCreate, CandidateResponse, CandidateUpdate
from app.services.candidate_service import CandidateService
from app.services.job_service import JobService
from app.schemas.job import CandidateMatchesResponse

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def create_candidate(
    payload: CandidateCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(CANDIDATES_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CandidateResponse:
    service = CandidateService(db)
    candidate = service.create_candidate(UUID(current_user.organization_id), payload, current_user=current_user)
    return CandidateResponse.model_validate(candidate)


@router.get("", response_model=list[CandidateResponse])
def list_candidates(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_any_permissions(CANDIDATES_READ, CANDIDATES_READ_OWN))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CandidateResponse]:
    service = CandidateService(db)
    candidates = service.list_candidates(
        UUID(current_user.organization_id),
        current_user,
        limit=limit,
        offset=offset,
    )
    return [CandidateResponse.model_validate(candidate) for candidate in candidates]


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_any_permissions(CANDIDATES_READ, CANDIDATES_READ_OWN))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CandidateResponse:
    service = CandidateService(db)
    candidate = service.get_candidate_by_id(candidate_id, UUID(current_user.organization_id), current_user)
    return CandidateResponse.model_validate(candidate)


@router.put("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(
    candidate_id: UUID,
    payload: CandidateUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(CANDIDATES_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CandidateResponse:
    service = CandidateService(db)
    candidate = service.update_candidate(
        candidate_id=candidate_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return CandidateResponse.model_validate(candidate)


@router.get("/{candidate_id}/matches", response_model=CandidateMatchesResponse)
def get_candidate_matches(
    candidate_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_any_permissions(CANDIDATES_READ, CANDIDATES_READ_OWN, ATS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CandidateMatchesResponse:
    service = JobService(db)
    return service.get_candidate_matches(
        candidate_id=candidate_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        limit=limit,
        offset=offset,
    )


@router.post("/{candidate_id}/rescore", status_code=status.HTTP_202_ACCEPTED)
def rescore_candidate_matches(
    candidate_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_any_permissions(CANDIDATES_UPDATE, ATS_RESCORE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, str]:
    service = JobService(db)
    service.dispatch_rescore_candidate(
        organization_id=UUID(current_user.organization_id),
        candidate_id=candidate_id,
    )
    return {"status": "queued", "candidate_id": str(candidate_id)}

