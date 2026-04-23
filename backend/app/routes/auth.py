from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.organization import Organization
from app.models.profile import Profile
from app.schemas.auth import UserRole
from app.schemas.auth_api import LoginRequest, SignupRequest, SignupResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    normalized_email = str(payload.email).lower()
    existing = db.scalar(select(Profile.id).where(func.lower(Profile.email) == normalized_email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    organization = Organization(name=f"Organization {uuid4().hex[:8]}")
    db.add(organization)
    db.flush()

    profile = Profile(
        organization_id=organization.id,
        email=normalized_email,
        role=UserRole.RECRUITER.value,
        password_hash=hash_password(payload.password),
    )
    db.add(profile)
    db.commit()
    return SignupResponse(message="Signup successful.")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    normalized_email = str(payload.email).lower()
    profile = db.scalar(select(Profile).where(func.lower(Profile.email) == normalized_email))
    if profile is None or not verify_password(payload.password, profile.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    token = create_access_token(
        subject=str(profile.id),
        extra_claims={
            "role": profile.role,
            "organization_id": str(profile.organization_id),
        },
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=UserRole(profile.role),
        organization_id=str(profile.organization_id),
    )
