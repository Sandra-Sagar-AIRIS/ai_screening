"""AIR-38: Candidate notes at /api/v1/candidates/{id}/notes (wraps note interactions)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.candidate_management.schemas import NoteCreate, NoteListResponse, NoteResponse
from app.candidate_management.service import CandidateManagementService
from app.core.dependencies import get_current_user, require_any_permissions, require_permission
from app.core.permissions import CANDIDATES_READ, CANDIDATES_READ_OWN, CANDIDATES_UPDATE
from app.db.session import get_db
from app.schemas.auth import CurrentUser

router = APIRouter(prefix="/candidates", tags=["candidate-notes"])


def _workspace_id_header(x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id")) -> UUID:
    if not x_workspace_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="X-Workspace-Id header is required.")
    try:
        return UUID(x_workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-Workspace-Id.") from exc


def _service(db: Session) -> CandidateManagementService:
    return CandidateManagementService(db)


def _is_admin(current_user: CurrentUser) -> bool:
    return (getattr(current_user, "role", "") or "").lower() in {"admin", "agency_admin"}


@router.get("/{candidate_id}/notes", response_model=NoteListResponse)
def list_candidate_notes(
    candidate_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_any_permissions(CANDIDATES_READ, CANDIDATES_READ_OWN))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    workspace_id: Annotated[UUID, Depends(_workspace_id_header)],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> NoteListResponse:
    """AIR-508: Org members with candidate access see notes; hidden notes only for admins."""
    service = _service(db)
    service.get_candidate(
        org_id=UUID(current_user.organization_id),
        workspace_id=workspace_id,
        candidate_id=candidate_id,
    )
    items, total = service.list_notes(
        org_id=UUID(current_user.organization_id),
        workspace_id=workspace_id,
        candidate_id=candidate_id,
        viewer_role=current_user.role,
        limit=limit,
        offset=offset,
    )
    return NoteListResponse(
        data=[NoteResponse.model_validate(item) for item in items],
        total=total,
    )


@router.post(
    "/{candidate_id}/notes",
    response_model=NoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_candidate_note(
    candidate_id: UUID,
    payload: NoteCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(CANDIDATES_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    workspace_id: Annotated[UUID, Depends(_workspace_id_header)],
) -> NoteResponse:
    """AIR-507: Create note with author (user_id) and timestamp."""
    service = _service(db)
    note = service.add_note(
        org_id=UUID(current_user.organization_id),
        workspace_id=workspace_id,
        candidate_id=candidate_id,
        actor_user_id=UUID(current_user.user_id),
        actor_role=current_user.role,
        content=payload.content,
    )
    return NoteResponse.model_validate(note)


@router.post("/{candidate_id}/notes/{note_id}/hide", response_model=NoteResponse)
def hide_candidate_note(
    candidate_id: UUID,
    note_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(require_permission(CANDIDATES_UPDATE))],
    workspace_id: Annotated[UUID, Depends(_workspace_id_header)],
) -> NoteResponse:
    """AIR-508: Admin-only soft-hide (metadata.hidden on interaction)."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    service = _service(db)
    service.get_candidate(
        org_id=UUID(current_user.organization_id),
        workspace_id=workspace_id,
        candidate_id=candidate_id,
    )
    note = service.soft_hide_note(
        org_id=UUID(current_user.organization_id),
        workspace_id=workspace_id,
        candidate_id=candidate_id,
        note_id=note_id,
        actor_user_id=UUID(current_user.user_id),
    )
    return NoteResponse.model_validate(note)
