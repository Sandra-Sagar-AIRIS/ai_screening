from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_user_permissions
from app.core.permissions import USERS_INVITE
from app.db.session import get_db
from app.models.profile import Profile
from app.schemas.auth import CurrentUser

router = APIRouter()


class UserListItem(BaseModel):
    id: str
    email: str
    role: str
    type: str
    created_at: datetime


class UserRoleUpdateRequest(BaseModel):
    role: str


def _require_users_manage_access(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if current_user.role == "admin":
        return current_user

    permissions = get_user_permissions(db, current_user.organization_id, current_user.role)
    if USERS_INVITE in permissions:
        return current_user

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: insufficient permissions.")


@router.get("", response_model=list[UserListItem])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(_require_users_manage_access)],
) -> list[UserListItem]:
    org_id = UUID(current_user.organization_id)
    stmt = (
        select(Profile)
        .where(Profile.organization_id == org_id)
        .order_by(func.lower(Profile.email).asc())
    )
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
    current_user: Annotated[CurrentUser, Depends(_require_users_manage_access)],
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

    role = payload.role.strip().lower()
    if not role:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="role must not be empty.")

    profile.role = role
    db.add(profile)
    db.commit()
    db.refresh(profile)

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
    current_user: Annotated[CurrentUser, Depends(_require_users_manage_access)],
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

    db.delete(profile)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
