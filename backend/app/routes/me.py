from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_user_permissions
from app.db.session import get_db
from app.schemas.auth import CurrentUser
from app.schemas.auth_api import MePermissionsResponse

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/permissions", response_model=MePermissionsResponse)
def get_me_permissions(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> MePermissionsResponse:
    if current_user.role is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: user role is required.")
    permissions = get_user_permissions(db, current_user.organization_id, current_user.role, user_id=current_user.user_id)
    return MePermissionsResponse(
        role=current_user.role,
        permissions=permissions,
    )
