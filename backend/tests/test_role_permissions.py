from __future__ import annotations

from uuid import uuid4

import pytest
from app.core.permissions import CANDIDATES_CREATE, JOBS_READ
from app.models.organization import Organization
from app.models.organization_role import OrganizationRole
from app.models.profile import Profile
from app.models.role_permission import RolePermission
from app.services.organization_role_service import ensure_default_organization_roles, get_role_id_by_key
from app.services.permission_service import PermissionService

pytestmark = pytest.mark.integration


def _create_org_and_user(db_session, *, role_key: str = "recruiter"):
    org = Organization(name=f"org-{uuid4().hex[:8]}")
    db_session.add(org)
    db_session.flush()

    ensure_default_organization_roles(db_session, org.id)
    db_session.flush()

    role_id = get_role_id_by_key(db_session, org.id, role_key)
    assert role_id is not None

    user = Profile(
        organization_id=org.id,
        email=f"user-{uuid4().hex[:8]}@example.com",
        role=role_key,
        role_id=role_id,
        type="internal",
        password_hash="test-password-hash",
    )
    db_session.add(user)
    db_session.flush()

    return org, user, role_id


def _add_role_permission(db_session, *, org_id, role_id, permission_code: str) -> None:
    db_session.add(RolePermission(organization_id=org_id, role_id=role_id, permission=permission_code))
    db_session.flush()


def test_role_permission_grants_access(db_session):
    org, user, role_id = _create_org_and_user(db_session, role_key="recruiter")
    _add_role_permission(db_session, org_id=org.id, role_id=role_id, permission_code=CANDIDATES_CREATE)

    service = PermissionService(db_session)
    effective = service.get_user_permissions(str(user.id))

    assert CANDIDATES_CREATE in effective
    assert service.can_user(str(user.id), str(org.id), CANDIDATES_CREATE) is True


def test_no_override_grant_role_only(db_session):
    """User-level overrides removed: extra permissions require role_permissions rows."""
    org, user, role_id = _create_org_and_user(db_session, role_key="recruiter")
    _add_role_permission(db_session, org_id=org.id, role_id=role_id, permission_code=CANDIDATES_CREATE)

    service = PermissionService(db_session)
    assert JOBS_READ not in service.get_user_permissions(str(user.id))
    assert service.can_user(str(user.id), str(org.id), JOBS_READ) is False
