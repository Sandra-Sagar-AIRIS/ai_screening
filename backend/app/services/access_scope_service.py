from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.client_job_access import ClientJobAccess
from app.models.job import Job
from app.models.job_vendor import JobVendor
from app.schemas.auth import CurrentUser, UserType


class AccessScopeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def is_client_user(self, current_user: CurrentUser) -> bool:
        return current_user.type == UserType.CLIENT

    def is_vendor_user(self, current_user: CurrentUser) -> bool:
        # Vendor scoping is driven by role (profiles.role), not user.type.
        return (current_user.role or "").strip().lower() == "vendor"

    def is_scoped_user(self, current_user: CurrentUser) -> bool:
        return self.is_client_user(current_user) or self.is_vendor_user(current_user)

    def allowed_job_ids_subquery(self, current_user: CurrentUser) -> Select[tuple[UUID]]:
        """
        Return a SQL subquery of allowed job IDs for scoped users.

        This avoids materializing Python lists of UUIDs and scales better for large mappings.
        """
        user_id = UUID(current_user.user_id)
        org_id = UUID(current_user.organization_id)

        if self.is_client_user(current_user):
            # Join through jobs so organization isolation is always enforced at SQL level.
            return (
                select(ClientJobAccess.job_id)
                .join(Job, Job.id == ClientJobAccess.job_id)
                .where(
                    ClientJobAccess.user_id == user_id,
                    Job.organization_id == org_id,
                )
            )

        if self.is_vendor_user(current_user):
            # Join through jobs so organization isolation is always enforced at SQL level.
            return (
                select(JobVendor.job_id)
                .join(Job, Job.id == JobVendor.job_id)
                .where(
                    JobVendor.vendor_id == user_id,
                    Job.organization_id == org_id,
                )
            )

        # Empty subquery for non-scoped users; callers should guard with is_scoped_user().
        return select(JobVendor.job_id).where(sa.false())
