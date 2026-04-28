from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_admin
from app.core.permissions import ALL_PERMISSIONS
from app.db.session import get_db
from app.models.role_permission import RolePermission
from app.schemas.auth import CurrentUser

router = APIRouter()

ROLE_KEYS: tuple[str, ...] = ("admin", "recruiter", "client_viewer")


class RolePermissionsUpdateRequest(BaseModel):
    permissions: list[str]


def _normalize_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in ROLE_KEYS:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid role.")
    return normalized


def _normalize_requested_permissions(values: list[str]) -> list[str]:
    allowed = set(ALL_PERMISSIONS)
    normalized = sorted({value.strip().lower() for value in values if value.strip()})
    invalid = [permission for permission in normalized if permission not in allowed]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid permissions: {', '.join(invalid)}",
        )
    return normalized


@router.get("", response_model=dict[str, list[str]])
def get_role_permissions(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_admin)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, list[str]]:
    org_id = UUID(current_user.organization_id)
    stmt = select(RolePermission.role, RolePermission.permission).where(RolePermission.organization_id == org_id)
    rows = db.execute(stmt).all()

    grouped = {role: [] for role in ROLE_KEYS}
    for role, permission in rows:
        role_key = role.strip().lower()
        permission_key = permission.strip().lower()
        if role_key in grouped and permission_key not in grouped[role_key]:
            grouped[role_key].append(permission_key)

    for role in grouped:
        grouped[role].sort()

    return grouped


@router.put("/{role}", response_model=dict[str, list[str]])
def update_role_permissions(
    role: str,
    payload: RolePermissionsUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_admin)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, list[str]]:
    org_id = UUID(current_user.organization_id)
    role_key = _normalize_role(role)
    permissions = _normalize_requested_permissions(payload.permissions)

    db.execute(
        delete(RolePermission).where(
            RolePermission.organization_id == org_id,
            RolePermission.role == role_key,
        )
    )

    for permission in permissions:
        db.add(RolePermission(organization_id=org_id, role=role_key, permission=permission))

    db.commit()
    return {role_key: permissions}
