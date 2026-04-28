from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.client_job_access import ClientJobAccess
from app.schemas.auth import CurrentUser, UserType


class AccessScopeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def is_client_user(self, current_user: CurrentUser) -> bool:
        return current_user.type == UserType.CLIENT

    def allowed_job_ids(self, current_user: CurrentUser) -> list[UUID]:
        if not self.is_client_user(current_user):
            return []
        stmt = select(ClientJobAccess.job_id).where(ClientJobAccess.user_id == UUID(current_user.user_id))
        return [job_id for job_id in self.db.scalars(stmt)]
