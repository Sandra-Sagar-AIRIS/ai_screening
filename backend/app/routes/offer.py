from __future__ import annotations

"""
PIPE-008: Offer Management Routes

All endpoints are nested under /pipelines/{pipeline_id}/offers for clear
association with the pipeline resource.

Reuses PIPELINE_READ / PIPELINE_UPDATE permissions — offer management is an
extension of the pipeline workflow, not a separate RBAC domain.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import PIPELINE_READ, PIPELINE_UPDATE
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.offer import (
    OfferCreate,
    OfferEventResponse,
    OfferResponse_,
    OfferRespondRequest,
    OfferRevise,
)
from app.services.offer_service import OfferService

router = APIRouter(
    prefix="/pipelines/{pipeline_id}/offers",
    tags=["offers"],
)


@router.post(
    "",
    response_model=OfferResponse_,
    status_code=status.HTTP_201_CREATED,
    summary="Create an offer for a pipeline at the offer stage (PIPE-008)",
)
def create_offer(
    pipeline_id: UUID,
    payload: OfferCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OfferResponse_:
    """
    Capture offer details (salary, currency, offer_date, expiry_date).

    The pipeline must be in the 'offer' stage.
    Only one active offer (pending/negotiating) is allowed per pipeline.
    """
    svc = OfferService(db)
    offer = svc.create_offer(
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return OfferResponse_.model_validate(offer)


@router.get(
    "",
    response_model=list[OfferResponse_],
    summary="List all offers (including history) for a pipeline (PIPE-008)",
)
def list_offers(
    pipeline_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[OfferResponse_]:
    """Return all offers for the pipeline, newest first (includes completed/declined history)."""
    svc = OfferService(db)
    offers = svc.list_offers(
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
    )
    return [OfferResponse_.model_validate(o) for o in offers]


@router.get(
    "/active",
    response_model=OfferResponse_ | None,
    summary="Get the current active offer for a pipeline (PIPE-008)",
)
def get_active_offer(
    pipeline_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OfferResponse_ | None:
    """Return the pending/negotiating offer, or null if none exists."""
    svc = OfferService(db)
    offer = svc.get_active_offer(
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
    )
    if offer is None:
        return None
    return OfferResponse_.model_validate(offer)


@router.get(
    "/{offer_id}",
    response_model=OfferResponse_,
    summary="Get a specific offer by ID (PIPE-008)",
)
def get_offer(
    pipeline_id: UUID,
    offer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OfferResponse_:
    svc = OfferService(db)
    offer = svc.get_offer(
        offer_id=offer_id,
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
    )
    return OfferResponse_.model_validate(offer)


@router.patch(
    "/{offer_id}",
    response_model=OfferResponse_,
    summary="Revise offer details while pending or negotiating (PIPE-008)",
)
def revise_offer(
    pipeline_id: UUID,
    offer_id: UUID,
    payload: OfferRevise,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OfferResponse_:
    """
    Update salary, currency, or expiry_date while the offer is still open.
    Each revision is recorded in the audit log; first revision moves status to 'negotiating'.
    """
    svc = OfferService(db)
    offer = svc.revise_offer(
        offer_id=offer_id,
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return OfferResponse_.model_validate(offer)


@router.post(
    "/{offer_id}/respond",
    response_model=OfferResponse_,
    summary="Submit candidate response to an offer (PIPE-008)",
)
def respond_to_offer(
    pipeline_id: UUID,
    offer_id: UUID,
    payload: OfferRespondRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OfferResponse_:
    """
    Record the candidate's response:

    - **accepted**: auto-transitions pipeline to 'placed'.
    - **declined**: requires decline_reason (≥ 10 chars); auto-transitions pipeline
      to 'rejected' (or back to previous stage if revert_to_previous_stage=true).
    - **negotiating**: keeps pipeline in 'offer' stage; allows further revisions.
    """
    svc = OfferService(db)
    offer = svc.respond_to_offer(
        offer_id=offer_id,
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
        payload=payload,
    )
    return OfferResponse_.model_validate(offer)


@router.get(
    "/{offer_id}/history",
    response_model=list[OfferEventResponse],
    summary="Get the full event history for a specific offer (PIPE-008)",
)
def get_offer_history(
    pipeline_id: UUID,
    offer_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[OfferEventResponse]:
    svc = OfferService(db)
    events = svc.get_offer_events(
        offer_id=offer_id,
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
    )
    return [OfferEventResponse.model_validate(e) for e in events]


@router.get(
    "/history/all",
    response_model=list[OfferEventResponse],
    summary="Get the full offer event timeline for a pipeline (PIPE-008)",
)
def get_pipeline_offer_history(
    pipeline_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(PIPELINE_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[OfferEventResponse]:
    """All offer events across all offers for this pipeline, chronological order."""
    svc = OfferService(db)
    events = svc.get_pipeline_offer_history(
        pipeline_id=pipeline_id,
        organization_id=UUID(current_user.organization_id),
        current_user=current_user,
    )
    return [OfferEventResponse.model_validate(e) for e in events]
