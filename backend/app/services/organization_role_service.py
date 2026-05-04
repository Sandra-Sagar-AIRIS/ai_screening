"""Helpers for tenant-scoped organization roles (system + custom)."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.organization_role import OrganizationRole

# Default roles every org has (keys match historical profile.role / role_permissions).
DEFAULT_ORG_ROLES: tuple[tuple[str, str], ...] = (
    ("Admin", "admin"),
    ("Recruiter", "recruiter"),
    ("Client viewer", "client_viewer"),
    ("Vendor", "vendor"),
)


def slugify_role_name(name: str) -> str:
    """URL-safe key from a display name (e.g. 'Senior Recruiter' -> 'senior_recruiter')."""
    raw = re.sub(r"[^a-z0-9]+", "_", name.strip().lower())
    return (raw.strip("_") or "role")[:64]


def ensure_default_organization_roles(db: Session, organization_id: UUID) -> None:
    """Create built-in organization_roles rows if missing (idempotent)."""
    for display_name, key in DEFAULT_ORG_ROLES:
        exists = db.scalar(
            select(OrganizationRole.id).where(
                OrganizationRole.organization_id == organization_id,
                OrganizationRole.key == key,
            )
        )
        if exists is None:
            db.add(
                OrganizationRole(
                    organization_id=organization_id,
                    name=display_name,
                    key=key,
                )
            )


def get_role_id_by_key(db: Session, organization_id: UUID, role_key: str) -> UUID | None:
    key = role_key.strip().lower()
    if not key:
        return None
    return db.scalar(
        select(OrganizationRole.id).where(
            OrganizationRole.organization_id == organization_id,
            OrganizationRole.key == key,
        )
    )


def make_unique_role_key(db: Session, organization_id: UUID, base_key: str) -> str:
    """Ensure `key` is unique within the org (appends _2, _3, ... if needed)."""
    candidate = base_key[:64]
    n = 1
    while True:
        taken = db.scalar(
            select(OrganizationRole.id).where(
                OrganizationRole.organization_id == organization_id,
                OrganizationRole.key == candidate,
            )
        )
        if taken is None:
            return candidate
        n += 1
        suffix = f"_{n}"
        candidate = f"{base_key[: 64 - len(suffix)]}{suffix}"
