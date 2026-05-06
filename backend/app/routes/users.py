from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_user_permissions
from app.core.permissions import USERS_DELETE, USERS_INVITE, USERS_UPDATE_ROLE
from app.db.session import get_db
from app.models.organization_role import OrganizationRole
from app.models.profile import Profile
from app.schemas.auth import CurrentUser
from app.services.organization_role_service import get_role_id_by_key
from app.services.permission_service import PermissionService, invalidate_permission_cache

router = APIRouter()


class UserListItem(BaseModel):
    id: str
    email: str
    role: str
    type: str
    created_at: datetime


class UserRoleUpdateRequest(BaseModel):
    role: str


def _normalized_role(value: str | None) -> str:
    return (value or "").strip().lower()


def _role_priority(role_key: str) -> int:
    # Higher number means higher privilege level.
    priorities: dict[str, int] = {
        "vendor": 10,
        "client_viewer": 20,
        "recruiter": 30,
        "admin": 100,
    }
    return priorities.get(role_key, 25)


def _require_users_invite_access(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    role_key = _normalized_role(current_user.role)
    if role_key == "admin":
        return current_user
    if role_key == "vendor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: vendor cannot manage users/roles.")

    permissions = get_user_permissions(db, current_user.organization_id, current_user.role, user_id=current_user.user_id)
    if USERS_INVITE in permissions:
        return current_user

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: insufficient permissions.")


def _require_users_update_role_access(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    role_key = _normalized_role(current_user.role)
    if role_key == "admin":
        return current_user
    if role_key == "vendor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: vendor cannot manage user roles.")

    permissions = get_user_permissions(db, current_user.organization_id, current_user.role, user_id=current_user.user_id)
    if USERS_UPDATE_ROLE in permissions:
        return current_user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: insufficient permissions.")


def _require_users_delete_access(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    role_key = _normalized_role(current_user.role)
    if role_key == "admin":
        return current_user
    if role_key == "vendor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: vendor cannot delete users.")

    permissions = get_user_permissions(db, current_user.organization_id, current_user.role, user_id=current_user.user_id)
    if USERS_DELETE in permissions:
        return current_user
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: insufficient permissions.")


@router.get("", response_model=list[UserListItem])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(_require_users_invite_access)],
    role: Annotated[str | None, Query(description="When set, return only users whose role key matches (case-insensitive)")] = None,
) -> list[UserListItem]:
    org_id = UUID(current_user.organization_id)
    stmt = select(Profile).where(Profile.organization_id == org_id)
    if role is not None and (key := role.strip().lower()):
        stmt = stmt.where(func.lower(Profile.role) == key)
    stmt = stmt.order_by(func.lower(Profile.email).asc())
    profiles = db.scalars(stmt).all()
    return [
        UserListItem(
            id=str(profile.id),
            email=profile.email,
            role=profile.role,
            type=profile.type,
            created_at=profile.created_at,
        )
        for profile in profiles
    ]


@router.patch("/{user_id}", response_model=UserListItem)
def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(_require_users_update_role_access)],
) -> UserListItem:
    org_id = UUID(current_user.organization_id)
    profile = db.scalar(
        select(Profile).where(
            Profile.id == user_id,
            Profile.organization_id == org_id,
        )
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    role_key = payload.role.strip().lower()
    if not role_key:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="role must not be empty.")

    role_id = get_role_id_by_key(db, org_id, role_key)
    if role_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unknown role for this organization.",
        )

    org_role = db.get(OrganizationRole, role_id)
    if org_role is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown role for this organization.")

    actor_role_key = _normalized_role(current_user.role)
    target_current_role_key = _normalized_role(profile.role)
    requested_role_key = _normalized_role(org_role.key)
    if actor_role_key != "admin":
        actor_priority = _role_priority(actor_role_key)
        target_priority = _role_priority(target_current_role_key)
        requested_priority = _role_priority(requested_role_key)
        if target_priority >= actor_priority or requested_priority >= actor_priority:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: cannot assign or modify roles at or above your own level.",
            )

    profile.role_id = role_id
    profile.role = org_role.key
    db.add(profile)
    db.commit()
    db.refresh(profile)
    invalidate_permission_cache(user_id=profile.id)

    return UserListItem(
        id=str(profile.id),
        email=profile.email,
        role=profile.role,
        type=profile.type,
        created_at=profile.created_at,
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_user(
    user_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(_require_users_delete_access)],
) -> Response:
    if user_id == UUID(current_user.user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot delete your own user.")

    org_id = UUID(current_user.organization_id)
    profile = db.scalar(
        select(Profile).where(
            Profile.id == user_id,
            Profile.organization_id == org_id,
        )
    )
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    actor_role_key = _normalized_role(current_user.role)
    target_role_key = _normalized_role(profile.role)
    if actor_role_key != "admin":
        actor_priority = _role_priority(actor_role_key)
        target_priority = _role_priority(target_role_key)
        if target_priority >= actor_priority:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: cannot delete users at or above your own role level.",
            )

    db.delete(profile)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{user_id}/permissions", response_model=list[str])
def get_effective_user_permissions(
    user_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(_require_users_invite_access)],
) -> list[str]:
    org_id = UUID(current_user.organization_id)
    profile = db.scalar(select(Profile).where(Profile.id == user_id, Profile.organization_id == org_id))
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    return PermissionService(db).get_user_permissions(str(user_id))
