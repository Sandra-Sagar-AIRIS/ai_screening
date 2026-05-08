from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.dependencies import get_user_permissions
from app.core.signup_permissions import seed_default_role_permissions
from app.services.organization_role_service import get_role_id_by_key
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.db.session import get_db
from app.models.auth_session import AuthSession
from app.models.organization import Organization
from app.models.profile import Profile
from app.schemas.auth import UserType
from app.schemas.auth_api import LoginRequest, RefreshRequest, SignupRequest, SignupResponse, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


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
    except Exception:
        logger.exception("Signup commit failed.")
        db.rollback()
        raise

    return SignupResponse(message="Signup successful.")


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    normalized_email = str(payload.email).lower()
    profile = db.scalar(select(Profile).where(func.lower(Profile.email) == normalized_email))
    if profile is None or not verify_password(payload.password, profile.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    org_limit = db.scalar(
        select(Organization.max_concurrent_sessions).where(Organization.id == profile.organization_id)
    )
    settings = get_settings()
    max_sessions = org_limit if org_limit and org_limit > 0 else settings.jwt_max_concurrent_sessions_default

    now = datetime.now(UTC)
    active_sessions = list(
        db.scalars(
            select(AuthSession)
            .where(
                AuthSession.user_id == profile.id,
                AuthSession.organization_id == profile.organization_id,
                AuthSession.revoked_at.is_(None),
                AuthSession.refresh_expires_at > now,
            )
            .order_by(AuthSession.last_used_at.asc(), AuthSession.created_at.asc())
        )
    )
    excess = max(0, (len(active_sessions) + 1) - max_sessions)
    for stale in active_sessions[:excess]:
        stale.revoked_at = now

    session_id = uuid4()
    access_token = create_access_token(
        subject=str(profile.id),
        extra_claims={
            "role": profile.role,
            "type": profile.type,
            "organization_id": str(profile.organization_id),
            "sid": str(session_id),
        },
    )
    refresh_token = create_refresh_token(
        subject=str(profile.id),
        extra_claims={
            "organization_id": str(profile.organization_id),
            "sid": str(session_id),
        },
    )
    refresh_payload = jwt.get_unverified_claims(refresh_token)
    refresh_exp = datetime.fromtimestamp(float(refresh_payload["exp"]), tz=UTC)
    db.add(
        AuthSession(
            id=session_id,
            organization_id=profile.organization_id,
            user_id=profile.id,
            refresh_token_hash=hashlib.sha256(refresh_token.encode("utf-8")).hexdigest(),
            refresh_expires_at=refresh_exp,
            last_used_at=now,
        )
    )
    db.commit()

    permissions = get_user_permissions(db, str(profile.organization_id), profile.role, user_id=str(profile.id))
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        role=profile.role,
        user_type=profile.type,
        organization_id=str(profile.organization_id),
        permissions=permissions,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenResponse:
    settings = get_settings()
    try:
        decoded = jwt.decode(payload.refresh_token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except ExpiredSignatureError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired.") from exc
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.") from exc

    if decoded.get("typ") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    sub = decoded.get("sub")
    org_id = decoded.get("organization_id")
    sid = decoded.get("sid")
    if not sub or not org_id or not sid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    try:
        user_id = UUID(str(sub))
        organization_id = UUID(str(org_id))
        session_id = UUID(str(sid))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.") from exc

    session = db.scalar(
        select(AuthSession).where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.organization_id == organization_id,
        )
    )
    if session is None or session.revoked_at is not None or session.refresh_expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is no longer valid.")
    presented_hash = hashlib.sha256(payload.refresh_token.encode("utf-8")).hexdigest()
    if presented_hash != session.refresh_token_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is no longer valid.")

    profile = db.scalar(select(Profile).where(Profile.id == user_id))
    if profile is None or profile.organization_id != organization_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated user not found.")

    new_access = create_access_token(
        subject=str(profile.id),
        extra_claims={
            "role": profile.role,
            "type": profile.type,
            "organization_id": str(profile.organization_id),
            "sid": str(session.id),
        },
    )
    new_refresh = create_refresh_token(
        subject=str(profile.id),
        extra_claims={
            "organization_id": str(profile.organization_id),
            "sid": str(session.id),
        },
    )
    refresh_payload = jwt.get_unverified_claims(new_refresh)
    session.refresh_token_hash = hashlib.sha256(new_refresh.encode("utf-8")).hexdigest()
    session.refresh_expires_at = datetime.fromtimestamp(float(refresh_payload["exp"]), tz=UTC)
    session.last_used_at = datetime.now(UTC)
    db.commit()

    permissions = get_user_permissions(db, str(profile.organization_id), profile.role, user_id=str(profile.id))
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        role=profile.role,
        user_type=profile.type,
        organization_id=str(profile.organization_id),
        permissions=permissions,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authentication token.")
    settings = get_settings()
    try:
        decoded = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        sid = decoded.get("sid")
        if decoded.get("typ") not in ("access", None) or not sid:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.")
        session_id = UUID(str(sid))
    except ExpiredSignatureError:
        return
    except (JWTError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.") from exc

    session = db.scalar(select(AuthSession).where(AuthSession.id == session_id))
    if session is not None and session.revoked_at is None:
        session.revoked_at = datetime.now(UTC)
        db.commit()
