from __future__ import annotations

import os
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ALL_PERMISSIONS
from app.core.permissions import normalize_permissions as _normalize_permissions_list
from app.models.profile import Profile
from app.models.role_permission import RolePermission

_CACHE_ENABLED = os.getenv("PERMISSION_CACHE_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
_CACHE_TTL_SECONDS = int(os.getenv("PERMISSION_CACHE_TTL_SECONDS", "60"))
_effective_permissions_cache: dict[str, tuple[float, list[str]]] = {}


def invalidate_permission_cache(user_id: UUID | str | None = None) -> None:
    """Best-effort cache invalidation after role_permission mutations."""

    if not _CACHE_ENABLED:
        return

    if user_id is None:
        _effective_permissions_cache.clear()
        return

    _effective_permissions_cache.pop(str(user_id), None)


class PermissionService:
    def __init__(self, db: Session):
        self.db = db

    def _normalize_permission_code(self, permission_code: str) -> str | None:
        normalized = permission_code.strip().lower()
        if not normalized:
            return None
        if normalized not in ALL_PERMISSIONS:
            return None
        return normalized

    def can_user(self, user_id: str | UUID, org_id: str | UUID, permission_code: str) -> bool:
        """
        True if the user's org role has this permission in role_permissions.
        No user-level overrides — role_permissions is the only source of truth.
        """
        normalized_code = self._normalize_permission_code(permission_code)
        if normalized_code is None:
            return False

        user_uuid = UUID(str(user_id))
        org_uuid = UUID(str(org_id))

        profile = self.db.scalar(select(Profile).where(Profile.id == user_uuid))
        if profile is None or profile.organization_id != org_uuid:
            return False

        row = self.db.scalar(
            select(RolePermission.id).where(
                RolePermission.organization_id == org_uuid,
                RolePermission.role_id == profile.role_id,
                RolePermission.permission == normalized_code,
            )
        )
        return row is not None

    def get_user_permissions(self, user_id: str | UUID) -> list[str]:
        """
        Effective permissions: all permission strings on the user's org role (role_permissions only).
        """
        user_uuid = UUID(str(user_id))
        cache_key = str(user_uuid)
        if _CACHE_ENABLED:
            cached = _effective_permissions_cache.get(cache_key)
            if cached is not None:
                expires_at, permissions = cached
                if expires_at > datetime.now().timestamp():
                    return permissions

        profile = self.db.scalar(select(Profile).where(Profile.id == user_uuid))
        if profile is None:
            return []

        stmt = select(RolePermission.permission).where(
            RolePermission.organization_id == profile.organization_id,
            RolePermission.role_id == profile.role_id,
        )
        values = [p for p in self.db.scalars(stmt).all()]
        effective_permissions = _normalize_permissions_list(values)

        if _CACHE_ENABLED:
            _effective_permissions_cache[cache_key] = (
                datetime.now().timestamp() + _CACHE_TTL_SECONDS,
                effective_permissions,
            )

        return effective_permissions
