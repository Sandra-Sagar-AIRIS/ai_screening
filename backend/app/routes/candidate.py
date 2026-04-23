from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_recruiter_or_admin
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.candidate import CandidateCreate, CandidateResponse, CandidateUpdate
from app.services.candidate_service import CandidateService

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
def create_candidate(
    payload: CandidateCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_recruiter_or_admin)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CandidateResponse:
    service = CandidateService(db)
    candidate = service.create_candidate(UUID(current_user.organization_id), payload)
    return CandidateResponse.model_validate(candidate)


@router.get("", response_model=list[CandidateResponse])
def list_candidates(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CandidateResponse]:
    service = CandidateService(db)
    candidates = service.list_candidates(UUID(current_user.organization_id), limit=limit, offset=offset)
    return [CandidateResponse.model_validate(candidate) for candidate in candidates]


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CandidateResponse:
    service = CandidateService(db)
    candidate = service.get_candidate_by_id(candidate_id, UUID(current_user.organization_id))
    return CandidateResponse.model_validate(candidate)


@router.put("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(
    candidate_id: UUID,
    payload: CandidateUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_recruiter_or_admin)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CandidateResponse:
    service = CandidateService(db)
    candidate = service.update_candidate(
        candidate_id=candidate_id,
        organization_id=UUID(current_user.organization_id),
        payload=payload,
    )
    return CandidateResponse.model_validate(candidate)

