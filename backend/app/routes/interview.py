from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import INTERVIEWS_CREATE, INTERVIEWS_READ, INTERVIEWS_UPDATE
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.interview import InterviewCreate, InterviewResponse, InterviewUpdate
from app.services.interview_service import InterviewService

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
def create_interview(
    payload: InterviewCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewResponse:
    service = InterviewService(db)
    interview = service.create_interview(UUID(current_user.organization_id), current_user, payload)
    return InterviewResponse.model_validate(interview)


@router.get("", response_model=list[InterviewResponse])
def list_interviews(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    pipeline_id: Annotated[UUID | None, Query()] = None,
) -> list[InterviewResponse]:
    service = InterviewService(db)
    interviews = service.list_interviews(
        UUID(current_user.organization_id),
        current_user,
        limit=limit,
        offset=offset,
        pipeline_id=pipeline_id,
    )
    return [InterviewResponse.model_validate(i) for i in interviews]


@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewResponse:
    service = InterviewService(db)
    interview = service.get_interview_by_id(interview_id, UUID(current_user.organization_id), current_user)
    return InterviewResponse.model_validate(interview)


@router.put("/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: UUID,
    payload: InterviewUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(INTERVIEWS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InterviewResponse:
    service = InterviewService(db)
    interview = service.update_interview(
        interview_id=interview_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return InterviewResponse.model_validate(interview)
