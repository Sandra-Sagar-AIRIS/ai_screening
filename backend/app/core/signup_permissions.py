"""Default organization_roles + role_permissions rows seeded for each new organization."""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

_RECRUITER_DEFAULTS: tuple[str, ...] = (
    "jobs:read",
    "jobs:update",
    "candidates:create",
    "candidates:read",
    "candidates:update",
    # Listing pipelines (dashboard, job detail candidates) requires read; update alone is not enough.
    "pipeline:read",
    "pipeline:create",
    "pipeline:update",
    "ats:read",
    "ats:rescore",
    # AI Screening layer
    "ai_screening:create",
    "ai_screening:read",
    "ai_screening:update",
    "ai_screening:evaluate",
    # Interview workflow
    "interviews:create",
    "interviews:read",
    "interviews:update",
    "interviews:feedback",
    "interviews:claim",
    "interviews:panel",
    "interviews:copilot",
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


from app.models.organization_role import OrganizationRole

def seed_default_role_permissions(db: Session, organization_id: UUID) -> None:
    """
    Create default org roles and role_permissions. Idempotent.
    """
    ensure_default_organization_roles(db, organization_id)
    db.flush()

    # 1. Get all roles for this organization
    roles = db.scalars(select(OrganizationRole).where(OrganizationRole.organization_id == organization_id)).all()
    role_map = {r.key: r.id for r in roles}

    # 2. Get existing permissions
    existing_pairs = {
        (row.role_id, row.permission)
        for row in db.execute(
            select(RolePermission.role_id, RolePermission.permission).where(RolePermission.organization_id == organization_id)
        ).all()
    }

    inserted_count = 0
    for role_key, permission in iter_default_role_permission_pairs():
        role_id = role_map.get(role_key)
        if not role_id:
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

    logger.info(
        "Seeded default role permissions",
        extra={
            "organization_id": str(organization_id),
            "inserted_count": inserted_count,
        },
    )


def backfill_all_organizations(db: Session) -> None:
    """Re-run seed_default_role_permissions for every organization in the database.

    Idempotent — only inserts missing (role_id, permission) rows, never deletes.
    Called once at application startup so new permissions added to ALL_PERMISSIONS
    or _RECRUITER_DEFAULTS are automatically propagated to existing orgs.
    """
    from app.models.organization import Organization  # local import avoids circular dep

    org_ids = db.scalars(select(Organization.id)).all()
    logger.info("permission_backfill.start org_count=%d", len(org_ids))
    total_inserted = 0
    for org_id in org_ids:
        try:
            seed_default_role_permissions(db, org_id)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning("permission_backfill.org_failed org_id=%s: %s", org_id, exc)
    logger.info("permission_backfill.complete total_orgs=%d", len(org_ids))
