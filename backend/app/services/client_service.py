from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.client import Client
from app.schemas.client import ClientCreate, ClientUpdate


class ClientService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_client(self, organization_id: UUID, payload: ClientCreate) -> Client:
        email_val: str | None = None
        if payload.email is not None:
            email_val = str(payload.email).lower()

        client = Client(
            organization_id=organization_id,
            name=payload.name.strip(),
            legal_name=payload.legal_name,
            industry=payload.industry,
            website=payload.website,
            email=email_val,
            phone=payload.phone,
            location=payload.location,
            notes=payload.notes,
        )
        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)
        return client

    def list_clients(self, organization_id: UUID, limit: int = 50, offset: int = 0) -> list[Client]:
        stmt: Select[tuple[Client]] = (
            select(Client)
            .where(
                Client.organization_id == organization_id,
                Client.is_deleted.is_(False),
            )
            .order_by(Client.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def get_client_by_id(self, client_id: UUID, organization_id: UUID) -> Client:
        stmt: Select[tuple[Client]] = select(Client).where(
            Client.id == client_id,
            Client.organization_id == organization_id,
            Client.is_deleted.is_(False),
        )
        client = self.db.scalar(stmt)
        if client is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Client not found.",
            )
        return client

    def update_client(
        self,
        client_id: UUID,
        organization_id: UUID,
        payload: ClientUpdate,
    ) -> Client:
        client = self.get_client_by_id(client_id, organization_id)

        update_data = payload.model_dump(exclude_unset=True)
        if "name" in update_data and update_data["name"] is not None:
            update_data["name"] = str(update_data["name"]).strip()
        if "email" in update_data and update_data["email"] is not None:
            update_data["email"] = str(update_data["email"]).lower()

        for field, value in update_data.items():
            setattr(client, field, value)

        self.db.add(client)
        self.db.commit()
        self.db.refresh(client)
        return client
