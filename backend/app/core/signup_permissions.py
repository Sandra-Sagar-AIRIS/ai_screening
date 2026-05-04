"""Default organization_roles + role_permissions rows seeded for each new organization."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ALL_PERMISSIONS
from app.models.role_permission import RolePermission
from app.services.organization_role_service import (
    ensure_default_organization_roles,
    get_role_id_by_key,
)

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

_VENDOR_DEFAULTS: tuple[str, ...] = (
    "candidates:read_own",
    "jobs:read_limited",
    "submissions:create",
    "submissions:read_own",
)


def iter_default_role_permission_pairs() -> Iterable[tuple[str, str]]:
    """(role_key, permission) pairs to ensure for a new organization."""
    for permission in ALL_PERMISSIONS:
        yield ("admin", permission)
    for permission in _RECRUITER_DEFAULTS:
        yield ("recruiter", permission)
    for permission in _CLIENT_DEFAULTS:
        yield ("client_viewer", permission)
    for permission in _VENDOR_DEFAULTS:
        yield ("vendor", permission)


def seed_default_role_permissions(db: Session, organization_id: UUID) -> None:
    """
    Create default org roles and role_permissions. Idempotent.
    """
    ensure_default_organization_roles(db, organization_id)
    db.flush()

    existing_pairs = set(
        db.execute(
            select(RolePermission.role_id, RolePermission.permission).where(
                RolePermission.organization_id == organization_id
            )
        ).all()
    )

    inserted_count = 0
    for role_key, permission in iter_default_role_permission_pairs():
        role_id = get_role_id_by_key(db, organization_id, role_key)
        if role_id is None:
            continue
        if (role_id, permission) in existing_pairs:
            continue
        db.add(
            RolePermission(
                organization_id=organization_id,
                role_id=role_id,
                permission=permission,
            )
        )
        existing_pairs.add((role_id, permission))
        inserted_count += 1

    print(f"[signup_permissions] organization_id={organization_id} inserted={inserted_count}")
