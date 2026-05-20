from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import (
    CLIENTS_CREATE,
    CLIENTS_DELETE,
    CLIENTS_READ,
    CLIENTS_UPDATE,
)
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.client import (
    ClientCreate,
    ClientRecruiterResponse,
    ClientResponse,
    ClientUpdate,
)
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


def _recruiter_id_for_user(current_user: CurrentUser) -> UUID | None:
    """Return the caller's user_id when they are a recruiter (not admin). Used for visibility scoping."""
    role = (current_user.role or "").lower().strip()
    if role in ("admin", "superadmin"):
        return None
    return UUID(current_user.user_id)


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(CLIENTS_CREATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ClientResponse:
    service = ClientService(db)
    client = service.create_client(
        organization_id=UUID(current_user.organization_id),
        payload=payload,
        created_by=UUID(current_user.user_id),
    )
    return ClientResponse.model_validate(client)


@router.get("", response_model=list[ClientResponse])
def list_clients(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(CLIENTS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ClientResponse]:
    service = ClientService(db)
    clients = service.list_clients(
        organization_id=UUID(current_user.organization_id),
        limit=limit,
        offset=offset,
        recruiter_id=_recruiter_id_for_user(current_user),
    )
    return [ClientResponse.model_validate(c) for c in clients]


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(CLIENTS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ClientResponse:
    service = ClientService(db)
    client = service.get_client_by_id(
        client_id=client_id,
        organization_id=UUID(current_user.organization_id),
        recruiter_id=_recruiter_id_for_user(current_user),
    )
    return ClientResponse.model_validate(client)


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(CLIENTS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ClientResponse:
    service = ClientService(db)
    client = service.update_client(
        client_id=client_id,
        organization_id=UUID(current_user.organization_id),
        payload=payload,
        requester_id=UUID(current_user.user_id),
    )
    return ClientResponse.model_validate(client)


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(CLIENTS_DELETE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    service = ClientService(db)
    service.soft_delete_client(
        client_id=client_id,
        organization_id=UUID(current_user.organization_id),
        deleted_by=UUID(current_user.user_id),
    )


# ── Recruiter assignment endpoints ────────────────────────────────────────────


@router.get("/{client_id}/recruiters", response_model=list[ClientRecruiterResponse])
def list_client_recruiters(
    client_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(CLIENTS_READ))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[ClientRecruiterResponse]:
    service = ClientService(db)
    return service.list_assigned_recruiters(
        client_id=client_id,
        organization_id=UUID(current_user.organization_id),
    )


class _AssignRecruitersPayload:
    pass


from pydantic import BaseModel


class AssignRecruitersPayload(BaseModel):
    recruiter_ids: list[UUID]


@router.post("/{client_id}/recruiters", response_model=list[ClientRecruiterResponse])
def assign_recruiters(
    client_id: UUID,
    payload: AssignRecruitersPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(CLIENTS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[ClientRecruiterResponse]:
    service = ClientService(db)
    return service.assign_recruiters(
        client_id=client_id,
        organization_id=UUID(current_user.organization_id),
        recruiter_ids=payload.recruiter_ids,
        assigned_by=UUID(current_user.user_id),
    )


@router.delete("/{client_id}/recruiters/{recruiter_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_recruiter(
    client_id: UUID,
    recruiter_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(CLIENTS_UPDATE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    service = ClientService(db)
    service.remove_recruiter(
        client_id=client_id,
        organization_id=UUID(current_user.organization_id),
        recruiter_id=recruiter_id,
    )
