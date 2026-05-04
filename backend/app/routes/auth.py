from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.dependencies import get_user_permissions
from app.core.signup_permissions import seed_default_role_permissions
from app.services.organization_role_service import get_role_id_by_key
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.organization import Organization
from app.models.profile import Profile
from app.schemas.auth import UserType
from app.schemas.auth_api import LoginRequest, SignupRequest, SignupResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    normalized_email = str(payload.email).lower()
    org_name = payload.organization_name.strip()
    if not org_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="organization_name must not be empty.",
        )

    # 1) User must not exist before any org is created
    existing = db.scalar(select(Profile.id).where(func.lower(Profile.email) == normalized_email))
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    # 2) Create organization from client-provided name (db.flush for org.id)
    organization = Organization(name=org_name)
    db.add(organization)
    db.flush()

    # Default RBAC rows for this org (admin / recruiter / client) — same transaction as profile
    seed_default_role_permissions(db, organization.id)
    admin_role_id = get_role_id_by_key(db, organization.id, "admin")
    if admin_role_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default admin role is missing; cannot complete signup.",
        )

    # 3) First user for this org: admin, internal
    profile = Profile(
        organization_id=organization.id,
        email=normalized_email,
        role="admin",
        role_id=admin_role_id,
        type=UserType.INTERNAL,
        password_hash=hash_password(payload.password),
    )
    db.add(profile)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered.",
        ) from None
    except Exception as exc:
        print(f"COMMIT FAILED: {exc}")
        db.rollback()
        raise

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
            "type": profile.type,
            "organization_id": str(profile.organization_id),
        },
    )
    permissions = get_user_permissions(db, str(profile.organization_id), profile.role, user_id=str(profile.id))
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=profile.role,
        user_type=profile.type,
        organization_id=str(profile.organization_id),
        permissions=permissions,
    )
