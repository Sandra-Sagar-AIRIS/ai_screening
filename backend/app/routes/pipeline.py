from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import ORGANIZATION_MANAGE, PIPELINE_CREATE, PIPELINE_READ, PIPELINE_UPDATE
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.pipeline import PipelineCreate, PipelineResponse, PipelineStage, PipelineUpdate
from app.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipelines", tags=["pipelines"])


@router.post("", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    payload: PipelineCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PipelineResponse:
    service = PipelineService(db)
    pipeline = service.create_pipeline(UUID(current_user.organization_id), current_user, payload)
    return PipelineResponse.model_validate(pipeline)


@router.get("", response_model=list[PipelineResponse])
def list_pipelines(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    job_id: Annotated[UUID | None, Query()] = None,
    stage: Annotated[PipelineStage | None, Query()] = None,
) -> list[PipelineResponse]:
    service = PipelineService(db)
    pipelines = service.list_pipelines(
        UUID(current_user.organization_id),
        current_user,
        limit=limit,
        offset=offset,
        job_id=job_id,
        stage=stage,
    )
    return [PipelineResponse.model_validate(p) for p in pipelines]


@router.get("/{pipeline_id}", response_model=PipelineResponse)
def get_pipeline(
    pipeline_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PipelineResponse:
    service = PipelineService(db)
    pipeline = service.get_pipeline_by_id(pipeline_id, UUID(current_user.organization_id), current_user)
    return PipelineResponse.model_validate(pipeline)


@router.put("/{pipeline_id}", response_model=PipelineResponse)
def update_pipeline(
    pipeline_id: UUID,
    payload: PipelineUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PipelineResponse:
    service = PipelineService(db)
    pipeline = service.update_pipeline(
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return PipelineResponse.model_validate(pipeline)


@router.get("/debug/pipelines", response_model=list[PipelineResponse])
def debug_list_pipelines(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(ORGANIZATION_MANAGE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PipelineResponse]:
    settings = get_settings()
    if not settings.debug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")

    service = PipelineService(db)
    pipelines = service.list_all_pipelines_debug(limit=limit, offset=offset)
    return [PipelineResponse.model_validate(p) for p in pipelines]
