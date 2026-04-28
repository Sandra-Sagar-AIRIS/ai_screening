"""Default role_permissions rows seeded for each new organization at signup."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ALL_PERMISSIONS
from app.models.role_permission import RolePermission

# User-specified defaults for non-admin roles (MVP).
_RECRUITER_DEFAULTS: tuple[str, ...] = (
    "jobs:read",
    "candidates:create",
    "candidates:read",
    "pipeline:update",
)
_CLIENT_DEFAULTS: tuple[str, ...] = (
    "jobs:read",
    "pipeline:read",
)


def iter_default_role_permission_pairs() -> Iterable[tuple[str, str]]:
    """All (role, permission) pairs to insert for a new organization."""
    for permission in ALL_PERMISSIONS:
        yield ("admin", permission)
    for permission in _RECRUITER_DEFAULTS:
        yield ("recruiter", permission)
    for permission in _CLIENT_DEFAULTS:
        yield ("client", permission)


def seed_default_role_permissions(db: Session, organization_id: UUID) -> None:
    """
    Insert default role_permissions for the organization.
    Uses ORM inserts only. Skips rows that already exist for idempotency.
    """
    desired_pairs = list(iter_default_role_permission_pairs())
    if not desired_pairs:
        print(f"[signup_permissions] organization_id={organization_id} inserted=0")
        return

    existing_pairs = set(
        db.execute(
            select(RolePermission.role, RolePermission.permission).where(
                RolePermission.organization_id == organization_id
            )
        ).all()
    )

    inserted_count = 0
    for role, permission in desired_pairs:
        if (role, permission) in existing_pairs:
            continue
        db.add(
            RolePermission(
                organization_id=organization_id,
                role=role,
                permission=permission,
            )
        )
        inserted_count += 1

    print(f"[signup_permissions] organization_id={organization_id} inserted={inserted_count}")
