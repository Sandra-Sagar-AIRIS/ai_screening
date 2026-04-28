from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import USERS_INVITE
from app.core.security import hash_password
from app.db.session import get_db
from app.models.invite import Invite
from app.models.profile import Profile
from app.schemas.auth import CurrentUser, UserType
from app.schemas.invite import (
    InviteAcceptRequest,
    InviteAcceptResponse,
    InviteCreate,
    InviteCreateResponse,
    InviteResponse,
)
from app.services.email_service import send_invite_email

logger = logging.getLogger(__name__)

router = APIRouter()


def _generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


@router.post("", response_model=InviteCreateResponse, status_code=status.HTTP_201_CREATED)
def create_invite(
    payload: InviteCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[CurrentUser, Depends(require_permission(USERS_INVITE))],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> InviteCreateResponse:
    normalized_email = str(payload.email).lower().strip()
    organization_id = UUID(current_user.organization_id)

    existing_profile = db.scalar(select(Profile.id).where(func.lower(Profile.email) == normalized_email))
    if existing_profile is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists.",
        )

    pending_invite = db.scalar(
        select(Invite.id).where(
            Invite.organization_id == organization_id,
            func.lower(Invite.email) == normalized_email,
            Invite.status == "pending",
        )
    )
    if pending_invite is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending invite already exists for this email.",
        )

    expires_at = datetime.now(UTC) + timedelta(days=payload.expires_in_days)
    invite = Invite(
        email=normalized_email,
        organization_id=organization_id,
        role=payload.role,
        token=_generate_invite_token(),
        status="pending",
        expires_at=expires_at,
    )
    db.add(invite)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to create invite due to a unique constraint conflict.",
        ) from None
    db.refresh(invite)

    try:
        send_invite_email(normalized_email, invite.token)
    except Exception:
        logger.exception("Invite email failed for %s; invite was still created.", normalized_email)

    return InviteCreateResponse(
        message="Invite created successfully.",
        invite=InviteResponse(
            id=str(invite.id),
            email=invite.email,
            organization_id=str(invite.organization_id),
            role=invite.role,
            status=invite.status,
            expires_at=invite.expires_at,
            created_at=invite.created_at,
        ),
        token=invite.token,
    )


@router.post("/accept", response_model=InviteAcceptResponse)
def accept_invite(
    payload: InviteAcceptRequest,
    db: Annotated[Session, Depends(get_db)],
) -> InviteAcceptResponse:
    invite = db.scalar(select(Invite).where(Invite.token == payload.token))
    if invite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found.")
    if invite.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite has already been accepted.")
    if invite.expires_at < datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Invite has expired.")

    existing_profile = db.scalar(select(Profile.id).where(func.lower(Profile.email) == invite.email))
    if existing_profile is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists for this invite email.")

    profile = Profile(
        organization_id=invite.organization_id,
        email=invite.email,
        role=invite.role,
        type=UserType.INTERNAL,
        password_hash=hash_password(payload.password),
    )
    invite.status = "accepted"

    db.add(profile)
    db.add(invite)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Failed to accept invite due to a data conflict.",
        ) from None

    return InviteAcceptResponse(message="Invite accepted successfully.")
