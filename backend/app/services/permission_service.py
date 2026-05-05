from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
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
_DEBUG_LOG_PATH = Path(__file__).resolve().parents[2] / "debug-f65d2f.log"


def _debug_log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    payload = {
        "sessionId": "f65d2f",
        "runId": "pre-fix",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with _DEBUG_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except Exception:
        pass


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
        # region agent log
        _debug_log(
            "H3",
            "backend/app/services/permission_service.py:can_user:profile",
            "Profile lookup during permission check",
            {
                "profile_found": profile is not None,
                "org_match": bool(profile is not None and profile.organization_id == org_uuid),
                "has_role_id": bool(profile is not None and getattr(profile, "role_id", None)),
                "permission": normalized_code or "",
            },
        )
        # endregion
        if profile is None or profile.organization_id != org_uuid:
            return False

        row = self.db.scalar(
            select(RolePermission.id).where(
                RolePermission.organization_id == org_uuid,
                RolePermission.role_id == profile.role_id,
                RolePermission.permission == normalized_code,
            )
        )
        # region agent log
        _debug_log(
            "H4",
            "backend/app/services/permission_service.py:can_user:role_permission",
            "Role permission row lookup result",
            {
                "role_id_present": bool(getattr(profile, "role_id", None)),
                "permission": normalized_code or "",
                "permission_row_found": row is not None,
            },
        )
        # endregion
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
