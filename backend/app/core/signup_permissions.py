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
    "jobs:update",
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
        yield ("client_viewer", permission)


from app.models.organization_role import OrganizationRole

def seed_default_role_permissions(db: Session, organization_id: UUID) -> None:
    """
    Insert default role_permissions for the organization.
    Uses ORM inserts only. Skips rows that already exist for idempotency.
    """
    desired_pairs = list(iter_default_role_permission_pairs())
    if not desired_pairs:
        print(f"[signup_permissions] organization_id={organization_id} inserted=0")
        return

    # 1. Get all roles for this organization
    roles = db.scalars(select(OrganizationRole).where(OrganizationRole.organization_id == organization_id)).all()
    role_map = {r.key: r.id for r in roles}

    # 2. Get existing permissions
    existing_pairs = set(
        db.execute(
            select(OrganizationRole.key, RolePermission.permission)
            .join(OrganizationRole, RolePermission.role_id == OrganizationRole.id)
            .where(RolePermission.organization_id == organization_id)
        ).all()
    )

    inserted_count = 0
    for role_key, permission in desired_pairs:
        if (role_key, permission) in existing_pairs:
            continue
        
        role_id = role_map.get(role_key)
        if not role_id:
            # Fallback: if role doesn't exist, we skip it (or we could create it, but usually roles should exist)
            continue

        db.add(
            RolePermission(
                organization_id=organization_id,
                role_id=role_id,
                permission=permission,
            )
        )
        inserted_count += 1

    print(f"[signup_permissions] organization_id={organization_id} inserted={inserted_count}")
