from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_recruiter_or_admin
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.client import ClientCreate, ClientResponse, ClientUpdate
from app.services.client_service import ClientService

router = APIRouter(prefix="/clients", tags=["clients"])


@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_recruiter_or_admin)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ClientResponse:
    service = ClientService(db)
    client = service.create_client(UUID(current_user.organization_id), payload)
    return ClientResponse.model_validate(client)


@router.get("", response_model=list[ClientResponse])
def list_clients(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ClientResponse]:
    service = ClientService(db)
    clients = service.list_clients(UUID(current_user.organization_id), limit=limit, offset=offset)
    return [ClientResponse.model_validate(client) for client in clients]


@router.get("/{client_id}", response_model=ClientResponse)
def get_client(
    client_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ClientResponse:
    service = ClientService(db)
    client = service.get_client_by_id(client_id, UUID(current_user.organization_id))
    return ClientResponse.model_validate(client)


@router.put("/{client_id}", response_model=ClientResponse)
def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_recruiter_or_admin)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ClientResponse:
    service = ClientService(db)
    client = service.update_client(
        client_id=client_id,
        organization_id=UUID(current_user.organization_id),
        payload=payload,
    )
    return ClientResponse.model_validate(client)
