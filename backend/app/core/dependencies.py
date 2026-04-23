from __future__ import annotations

from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.profile import Profile
from app.schemas.auth import CurrentUser, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


def _parse_role(raw_role: str | None) -> UserRole | None:
    if raw_role is None:
        return None
    try:
        return UserRole(raw_role.strip().lower())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user role in auth context.") from exc


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
) -> CurrentUser:
    """
    Resolve authenticated user context for tenant scoping.

    Current strategy:
    1) Prefer request.state.user if populated by auth middleware.
    2) Fallback to trusted upstream headers (API gateway/BFF).

    Replace with JWT verification once auth module is integrated.
    """
    state_user = getattr(request.state, "user", None)
    if state_user is not None:
        return CurrentUser(
            user_id=str(state_user.user_id),
            organization_id=str(state_user.organization_id),
            role=_parse_role(getattr(state_user, "role", None)),
        )

    if credentials is not None:
        settings = get_settings()
        token = credentials.credentials
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.")
            token_role = _parse_role(payload.get("role"))
            token_org_id = payload.get("organization_id")
        except JWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.") from exc

        try:
            user_uuid = UUID(str(user_id))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.") from exc

        profile = db.scalar(select(Profile).where(Profile.id == user_uuid))
        if profile is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authenticated user not found.")

        if x_organization_id and x_organization_id != str(profile.organization_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: organization scope mismatch.",
            )
        if token_org_id and token_org_id != str(profile.organization_id):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.")

        return CurrentUser(
            user_id=str(profile.id),
            organization_id=str(profile.organization_id),
            role=token_role or _parse_role(profile.role),
        )

    if not x_user_id or not x_organization_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authenticated user context.",
        )

    return CurrentUser(user_id=x_user_id, organization_id=x_organization_id, role=_parse_role(x_user_role))


def require_roles(allowed_roles: set[UserRole]):
    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: user role is required.")
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: insufficient permissions.")
        return current_user

    return _dependency


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return require_roles({UserRole.ADMIN})(current_user)


def require_recruiter_or_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return require_roles({UserRole.ADMIN, UserRole.RECRUITER})(current_user)

