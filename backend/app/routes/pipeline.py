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
from app.schemas.pipeline import (
    PipelineCreate,
    PipelineListMeta,
    PipelineListResponse,
    PipelineResponse,
    PipelineSortBy,
    PipelineSortDir,
    PipelineStage,
    PipelineStageHistoryResponse,
    PipelineStageTransitionRequest,
    PipelineStatus,
    PipelineStatusChangeRequest,
    PipelineStatusHistoryResponse,
    PipelineUpdate,
    WithdrawPipelineRequest,
)
from app.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipelines", tags=["pipelines"])
pipeline_router = APIRouter(prefix="/pipeline", tags=["pipelines"])


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


@router.get(
    "",
    response_model=PipelineListResponse,
    summary="List pipelines with filtering, sorting, and pagination (PIPE-004)",
)
def list_pipelines(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    job_id: Annotated[UUID | None, Query()] = None,
    candidate_id: Annotated[UUID | None, Query()] = None,
    stage: Annotated[PipelineStage | None, Query()] = None,
    pipeline_status: Annotated[PipelineStatus | None, Query(alias="status")] = None,
    sort_by: Annotated[PipelineSortBy, Query()] = PipelineSortBy.CREATED_AT,
    sort_dir: Annotated[PipelineSortDir, Query()] = PipelineSortDir.DESC,
) -> PipelineListResponse:
    """
    GET /api/v1/pipelines — PIPE-004

    Supports filtering by job_id, candidate_id, stage, and status.
    Sorting by created_at or stage_updated_at (asc/desc).
    Returns paginated data with total count and per-stage counts in metadata.
    All results are org-scoped; scoped users (vendor/client) see only allowed pipelines.
    """
    service = PipelineService(db)
    pipelines, total, stage_counts = service.list_pipelines_paginated(
        UUID(current_user.organization_id),
        current_user,
        limit=limit,
        offset=offset,
        job_id=job_id,
        candidate_id=candidate_id,
        stage=stage,
        pipeline_status=pipeline_status,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return PipelineListResponse(
        data=[PipelineResponse.model_validate(p) for p in pipelines],
        meta=PipelineListMeta(
            total=total,
            limit=limit,
            offset=offset,
            stage_counts=stage_counts,
        ),
    )


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


@router.patch("/{pipeline_id}", response_model=PipelineResponse)
@pipeline_router.patch("/{pipeline_id}", response_model=PipelineResponse)
def patch_pipeline(
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


@router.post(
    "/{pipeline_id}/transition",
    response_model=PipelineResponse,
    summary="Transition a pipeline to the next stage (PIPE-002)",
)
def transition_pipeline_stage(
    pipeline_id: UUID,
    payload: PipelineStageTransitionRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PipelineResponse:
    """
    Apply a validated, audited stage transition.

    Only transitions that follow the defined flow are accepted:
    applied → screening → interview → offer → placed / rejected.

    A rejection reason (≥ 10 characters) is **required** when transitioning to *rejected*.
    Invalid transitions return HTTP 422.
    """
    service = PipelineService(db)
    pipeline = service.transition_stage(
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return PipelineResponse.model_validate(pipeline)


@router.get(
    "/{pipeline_id}/history",
    response_model=list[PipelineStageHistoryResponse],
    summary="Fetch stage-transition audit history for a pipeline (PIPE-002)",
)
def get_pipeline_stage_history(
    pipeline_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[PipelineStageHistoryResponse]:
    service = PipelineService(db)
    history = service.get_stage_history(
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
    )
    return [PipelineStageHistoryResponse.model_validate(h) for h in history]


@router.post(
    "/{pipeline_id}/status",
    response_model=PipelineResponse,
    summary="Change the pipeline status (PIPE-003)",
)
def change_pipeline_status(
    pipeline_id: UUID,
    payload: PipelineStatusChangeRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PipelineResponse:
    """
    POST /api/v1/pipelines/{id}/status — PIPE-003

    Change the pipeline status (active → on_hold / withdrawn / closed).
    Each change is recorded in `pipeline_status_history` with actor + reason.
    Withdrawal requires a reason of ≥ 5 characters.
    Only administrators may reopen a closed pipeline.
    """
    service = PipelineService(db)
    pipeline = service.change_pipeline_status(
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return PipelineResponse.model_validate(pipeline)


@router.post(
    "/{pipeline_id}/withdraw",
    response_model=PipelineResponse,
    summary="Withdraw a pipeline (candidate-requested removal) (PIPE-003)",
)
def withdraw_pipeline(
    pipeline_id: UUID,
    payload: WithdrawPipelineRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> PipelineResponse:
    """
    POST /api/v1/pipelines/{id}/withdraw — PIPE-003

    Dedicated withdraw endpoint. Sets status to *withdrawn* and records an
    audit entry. Reason (≥ 5 chars) is required.
    """
    service = PipelineService(db)
    pipeline = service.withdraw_pipeline(
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return PipelineResponse.model_validate(pipeline)


@router.get(
    "/{pipeline_id}/status-history",
    response_model=list[PipelineStatusHistoryResponse],
    summary="Fetch status-change audit history for a pipeline (PIPE-003)",
)
def get_pipeline_status_history(
    pipeline_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[PipelineStatusHistoryResponse]:
    """
    GET /api/v1/pipelines/{id}/status-history — PIPE-003

    Returns every status change in chronological order, including previous
    status, new status, actor, and optional reason.
    """
    service = PipelineService(db)
    history = service.get_status_history(
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
    )
    return [PipelineStatusHistoryResponse.model_validate(h) for h in history]


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
