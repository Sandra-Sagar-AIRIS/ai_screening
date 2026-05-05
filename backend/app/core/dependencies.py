from __future__ import annotations

import logging
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.permissions import normalize_permissions
from app.db.session import get_db
from app.models.organization_role import OrganizationRole
from app.models.profile import Profile
from app.models.role_permission import RolePermission
from app.schemas.auth import CurrentUser, UserType
from app.services.permission_service import PermissionService

bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)

ROLE_ALIASES: dict[str, tuple[str, ...]] = {
    "client_viewer": ("client_viewer", "client"),
    "client": ("client", "client_viewer"),
}


def _parse_role(raw_role: str | None) -> str | None:
    if raw_role is None:
        return None
    parsed = raw_role.strip().lower()
    if not parsed:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user role in auth context.")
    return parsed


def _parse_user_type(raw_type: str | None) -> str:
    if raw_type is None:
        return UserType.INTERNAL
    try:
        parsed = raw_type.strip().lower()
        if parsed not in (UserType.INTERNAL, UserType.CLIENT):
            raise ValueError("invalid user type")
        return parsed
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user type in auth context.",
        ) from exc


def get_user_permissions(
    db: Session,
    organization_id: str,
    role: str | None,
    user_id: str | None = None,
) -> list[str]:
    """
    Effective permissions from role_permissions only.

    Prefer `user_id` when available (resolves the user's org role via profile.role_id).
    Legacy path uses `role` as organization_roles.key for the org.
    """

    if user_id is not None:
        return PermissionService(db).get_user_permissions(user_id)
    if role is None:
        return []
    role_key = role.strip().lower()
    if not role_key:
        return []
    try:
        org_uuid = UUID(organization_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid organization in auth context.") from exc
    role_keys = ROLE_ALIASES.get(role_key, (role_key,))
    stmt = (
        select(RolePermission.permission)
        .join(OrganizationRole, RolePermission.role_id == OrganizationRole.id)
        .where(
            RolePermission.organization_id == org_uuid,
            func.lower(OrganizationRole.key).in_(role_keys),
        )
    )
    values = [permission for permission in db.scalars(stmt)]
    normalized = normalize_permissions(values)
    logger.debug(
        "get_user_permissions org_id=%s role_in=%s role_keys=%s raw_rows=%s normalized=%s",
        organization_id,
        role,
        role_keys,
        len(values),
        len(normalized),
    )
    return normalized


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
    x_organization_id: str | None = Header(default=None, alias="X-Organization-Id"),
    x_user_role: str | None = Header(default=None, alias="X-User-Role"),
    x_user_type: str | None = Header(default=None, alias="X-User-Type"),
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
            type=_parse_user_type(getattr(state_user, "type", None)),
        )

    if credentials is not None:
        settings = get_settings()
        token = credentials.credentials
        try:
            payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token.")
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

        # Authorization uses DB truth: JWT `sub` only identifies the profile; stale/missing claims
        # on role/type would otherwise yield empty permission lookups or wrong client/internal behavior.
        return CurrentUser(
            user_id=str(profile.id),
            organization_id=str(profile.organization_id),
            role=_parse_role(profile.role),
            type=_parse_user_type(profile.type),
        )

    if not x_user_id or not x_organization_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authenticated user context.",
        )

    return CurrentUser(
        user_id=x_user_id,
        organization_id=x_organization_id,
        role=_parse_role(x_user_role),
        type=_parse_user_type(x_user_type),
    )


def require_roles(allowed_roles: set[str]):
    def _dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: user role is required.")
        if current_user.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: insufficient permissions.")
        return current_user

    return _dependency


def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return require_roles({"admin"})(current_user)


def require_recruiter_or_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    return require_roles({"admin", "recruiter"})(current_user)


def require_permission(permission: str):
    def _dependency(
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        permission_service = PermissionService(db)
        if not permission_service.can_user(current_user.user_id, current_user.organization_id, permission):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: insufficient permissions.")
        return current_user

    return _dependency


def require_any_permissions(*permissions: str):
    """
    Allows access if the user has at least one of the provided permissions.

    Useful for legacy endpoints where we need to support both "read all" and "read own".
    """

    permissions_normalized = tuple(p for p in permissions if p)
    def _dependency(
        current_user: CurrentUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> CurrentUser:
        permission_service = PermissionService(db)
        for permission in permissions_normalized:
            if permission_service.can_user(current_user.user_id, current_user.organization_id, permission):
                return current_user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: insufficient permissions.")

    return _dependency

