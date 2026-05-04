from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_user_permissions, require_admin
from app.core.permissions import ALL_PERMISSIONS, USERS_INVITE
from app.db.session import get_db
from app.models.organization_role import OrganizationRole
from app.models.role_permission import RolePermission
from app.schemas.auth import CurrentUser
from app.services.organization_role_service import make_unique_role_key, slugify_role_name
from app.services.permission_service import invalidate_permission_cache

router = APIRouter()


class OrganizationRoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    name: str
    key: str


class CreateOrganizationRoleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)


class RolePermissionsPayload(BaseModel):
    permissions: list[str]


def _normalize_requested_permissions(values: list[str]) -> list[str]:
    allowed = set(ALL_PERMISSIONS)
    normalized = sorted({value.strip().lower() for value in values if value and value.strip()})
    invalid = [permission for permission in normalized if permission not in allowed]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid permissions: {', '.join(invalid)}",
        )
    return normalized


def _require_admin_or_invite(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    """List roles for user-assignment UI (admins + users with users:invite)."""
    if current_user.role == "admin":
        return current_user
    if (current_user.role or "").strip().lower() == "vendor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")
    permissions = get_user_permissions(db, current_user.organization_id, current_user.role, user_id=current_user.user_id)
    if USERS_INVITE in permissions:
        return current_user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden.")


def _get_org_role_for_org(
    db: Session,
    *,
    organization_id: UUID,
    role_id: UUID,
) -> OrganizationRole:
    role = db.scalar(
        select(OrganizationRole).where(
            OrganizationRole.id == role_id,
            OrganizationRole.organization_id == organization_id,
        )
    )
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found.")
    return role


@router.get("", response_model=list[OrganizationRoleOut])
def list_organization_roles(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(_require_admin_or_invite)],
) -> list[OrganizationRole]:
    org_id = UUID(current_user.organization_id)
    return list(
        db.scalars(
            select(OrganizationRole)
            .where(OrganizationRole.organization_id == org_id)
            .order_by(OrganizationRole.name.asc())
        ).all()
    )


@router.post("", response_model=OrganizationRoleOut, status_code=status.HTTP_201_CREATED)
def create_organization_role(
    payload: CreateOrganizationRoleRequest,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_admin)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OrganizationRole:
    org_id = UUID(current_user.organization_id)
    base_key = slugify_role_name(payload.name)
    key = make_unique_role_key(db, org_id, base_key)
    row = OrganizationRole(
        organization_id=org_id,
        name=payload.name.strip(),
        key=key,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    invalidate_permission_cache()
    return row


@router.get("/{role_id}/permissions", response_model=list[str])
def get_role_permission_codes(
    role_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_admin)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[str]:
    org_id = UUID(current_user.organization_id)
    _get_org_role_for_org(db, organization_id=org_id, role_id=role_id)
    stmt = select(RolePermission.permission).where(
        RolePermission.organization_id == org_id,
        RolePermission.role_id == role_id,
    )
    codes = sorted({p for p in db.scalars(stmt).all()})
    return codes


@router.post("/{role_id}/permissions", response_model=list[str])
def replace_role_permissions(
    role_id: UUID,
    payload: RolePermissionsPayload,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_admin)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[str]:
    """
    Replace all permissions assigned to this role (tenant-isolated).
    """
    org_id = UUID(current_user.organization_id)
    _get_org_role_for_org(db, organization_id=org_id, role_id=role_id)
    permissions = _normalize_requested_permissions(payload.permissions)

    db.execute(
        delete(RolePermission).where(
            RolePermission.organization_id == org_id,
            RolePermission.role_id == role_id,
        )
    )
    for code in permissions:
        db.add(
            RolePermission(
                organization_id=org_id,
                role_id=role_id,
                permission=code,
            )
        )
    db.commit()
    invalidate_permission_cache()
    return permissions
