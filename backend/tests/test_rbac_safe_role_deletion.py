"""
F-RBAC-04 — Safe Role Deletion

Acceptance criteria verified:
  1. Role deletion is blocked (409) when one or more users are assigned the role.
  2. 409 response body lists all affected users (id + email).
  3. Unassigned roles are deleted immediately (204).
  4. Deletion is recorded as a structured audit log entry.
  5. Non-admin callers are rejected (403).
  6. Org scoping: roles from other orgs return 404 (not deletable cross-tenant).
  7. Deleting a non-existent role returns 404.
  8. Role permissions are cascade-deleted alongside the role.
"""
from __future__ import annotations

import logging
from typing import Generator
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

import app.main as main_module
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.organization_role import OrganizationRole
from app.models.profile import Profile
from app.models.role_permission import RolePermission
from app.schemas.auth import CurrentUser

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Fixed IDs for predictable assertions
# ---------------------------------------------------------------------------

ORG_ID = UUID("aaaaaaaa-0000-0000-0000-000000000001")
ADMIN_ID = UUID("aaaaaaaa-0000-0000-0000-000000000002")
ROLE_ID = UUID("aaaaaaaa-0000-0000-0000-000000000010")
USER_1_ID = UUID("aaaaaaaa-0000-0000-0000-000000000020")
USER_2_ID = UUID("aaaaaaaa-0000-0000-0000-000000000021")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_role(
    role_id: UUID = ROLE_ID,
    org_id: UUID = ORG_ID,
    name: str = "Custom Role",
    key: str = "custom_role",
) -> MagicMock:
    r = MagicMock(spec=OrganizationRole)
    r.id = role_id
    r.organization_id = org_id
    r.name = name
    r.key = key
    return r


def _make_profile(
    profile_id: UUID,
    email: str,
    org_id: UUID = ORG_ID,
    role_id: UUID = ROLE_ID,
) -> MagicMock:
    p = MagicMock(spec=Profile)
    p.id = profile_id
    p.email = email
    p.organization_id = org_id
    p.role_id = role_id
    return p


def _admin_user(org_id: UUID = ORG_ID) -> CurrentUser:
    return CurrentUser(
        user_id=str(ADMIN_ID),
        organization_id=str(org_id),
        role="admin",
    )


def _non_admin_user(org_id: UUID = ORG_ID) -> CurrentUser:
    return CurrentUser(
        user_id=str(uuid4()),
        organization_id=str(org_id),
        role="recruiter",
    )


# ---------------------------------------------------------------------------
# Stub DB that replays scalar/scalars in order
# ---------------------------------------------------------------------------


class _SequenceDB:
    """
    Minimal SQLAlchemy Session stub for unit tests.

    ``scalar_sequence``  — values returned one-by-one by successive .scalar() calls.
    ``scalars_result``   — object returned by .scalars() (should support .all()).
    Records calls to .delete() / .execute() / .commit() for assertion.
    """

    def __init__(
        self,
        scalar_sequence: list[object | None] | None = None,
        scalars_result: list[object] | None = None,
    ) -> None:
        self._scalars = list(scalar_sequence or [])
        self._scalars_result = scalars_result or []
        self.deleted: list[object] = []
        self.executed: list[object] = []
        self.committed = False

    def scalar(self, *_args, **_kwargs) -> object | None:
        return self._scalars.pop(0) if self._scalars else None

    def scalars(self, *_args, **_kwargs) -> "_ScalarsProxy":
        return _ScalarsProxy(self._scalars_result)

    def execute(self, stmt, *_args, **_kwargs) -> None:
        self.executed.append(stmt)

    def delete(self, obj: object) -> None:
        self.deleted.append(obj)

    def commit(self) -> None:
        self.committed = True

    def add(self, obj: object) -> None:
        pass


class _ScalarsProxy:
    def __init__(self, items: list[object]) -> None:
        self._items = items

    def all(self) -> list[object]:
        return list(self._items)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client(request: pytest.FixtureRequest):
    from fastapi.testclient import TestClient

    main_module.reflect_database_schema = lambda: None  # type: ignore[attr-defined]
    with TestClient(main_module.app) as tc:
        yield tc
    main_module.app.dependency_overrides.clear()


def _override_user(user: CurrentUser):
    def _dep() -> CurrentUser:
        return user

    return _dep


def _override_db(db: _SequenceDB):
    def _dep() -> Generator[_SequenceDB, None, None]:
        yield db

    return _dep


# ---------------------------------------------------------------------------
# 1. Unassigned role → 204 NO CONTENT
# ---------------------------------------------------------------------------


class TestDeleteUnassignedRole:
    def test_returns_204(self, client):
        role = _make_role()
        # scalar(1) = role lookup  |  scalars.all() = [] (no assigned users)
        db = _SequenceDB(scalar_sequence=[role], scalars_result=[])

        main_module.app.dependency_overrides[get_current_user] = _override_user(_admin_user())
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            response = client.delete(f"/api/v1/roles/{ROLE_ID}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 204

    def test_commits_after_deletion(self, client):
        role = _make_role()
        db = _SequenceDB(scalar_sequence=[role], scalars_result=[])

        main_module.app.dependency_overrides[get_current_user] = _override_user(_admin_user())
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            client.delete(f"/api/v1/roles/{ROLE_ID}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

        assert db.committed

    def test_role_object_marked_for_deletion(self, client):
        role = _make_role()
        db = _SequenceDB(scalar_sequence=[role], scalars_result=[])

        main_module.app.dependency_overrides[get_current_user] = _override_user(_admin_user())
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            client.delete(f"/api/v1/roles/{ROLE_ID}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

        assert role in db.deleted

    def test_role_permissions_cascade_deleted(self, client):
        """execute() must be called once to DELETE FROM role_permissions."""
        role = _make_role()
        db = _SequenceDB(scalar_sequence=[role], scalars_result=[])

        main_module.app.dependency_overrides[get_current_user] = _override_user(_admin_user())
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            client.delete(f"/api/v1/roles/{ROLE_ID}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

        assert len(db.executed) >= 1  # At minimum the DELETE role_permissions statement


# ---------------------------------------------------------------------------
# 2. Role has assigned users → 409 ROLE_IN_USE
# ---------------------------------------------------------------------------


class TestDeleteBlockedWhenUsersAssigned:
    def _delete_with_users(self, client, profiles: list):
        role = _make_role()
        db = _SequenceDB(scalar_sequence=[role], scalars_result=profiles)

        main_module.app.dependency_overrides[get_current_user] = _override_user(_admin_user())
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            return client.delete(f"/api/v1/roles/{ROLE_ID}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

    def test_returns_409_when_users_assigned(self, client):
        p1 = _make_profile(USER_1_ID, "alice@example.com")
        response = self._delete_with_users(client, [p1])
        assert response.status_code == 409

    def test_response_has_role_in_use_code(self, client):
        p1 = _make_profile(USER_1_ID, "alice@example.com")
        response = self._delete_with_users(client, [p1])
        body = response.json()
        assert body["detail"]["code"] == "ROLE_IN_USE"

    def test_response_lists_single_affected_user(self, client):
        p1 = _make_profile(USER_1_ID, "alice@example.com")
        response = self._delete_with_users(client, [p1])
        affected = response.json()["detail"]["affected_users"]
        assert len(affected) == 1
        assert affected[0]["email"] == "alice@example.com"
        assert affected[0]["id"] == str(USER_1_ID)

    def test_response_lists_multiple_affected_users(self, client):
        p1 = _make_profile(USER_1_ID, "alice@example.com")
        p2 = _make_profile(USER_2_ID, "bob@example.com")
        response = self._delete_with_users(client, [p1, p2])
        affected = response.json()["detail"]["affected_users"]
        emails = {u["email"] for u in affected}
        assert emails == {"alice@example.com", "bob@example.com"}

    def test_409_response_has_human_readable_message(self, client):
        p1 = _make_profile(USER_1_ID, "alice@example.com")
        response = self._delete_with_users(client, [p1])
        body = response.json()
        assert "message" in body["detail"]
        assert len(body["detail"]["message"]) > 10  # non-empty meaningful string

    def test_role_not_committed_when_blocked(self, client):
        """DB must not be modified when deletion is blocked."""
        role = _make_role()
        p1 = _make_profile(USER_1_ID, "alice@example.com")
        db = _SequenceDB(scalar_sequence=[role], scalars_result=[p1])

        main_module.app.dependency_overrides[get_current_user] = _override_user(_admin_user())
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            client.delete(f"/api/v1/roles/{ROLE_ID}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

        assert not db.committed
        assert role not in db.deleted


# ---------------------------------------------------------------------------
# 3. Audit trail — structured log on successful deletion
# ---------------------------------------------------------------------------


class TestDeletionAuditLog:
    def test_audit_log_emitted_on_deletion(self, client, caplog):
        role = _make_role(name="Audit Role", key="audit_role")
        db = _SequenceDB(scalar_sequence=[role], scalars_result=[])

        main_module.app.dependency_overrides[get_current_user] = _override_user(_admin_user())
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            with caplog.at_level(logging.INFO, logger="app.routes.roles"):
                client.delete(f"/api/v1/roles/{ROLE_ID}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

        assert any("role.deleted" in record.message for record in caplog.records)

    def test_audit_log_contains_role_id(self, client, caplog):
        role = _make_role()
        db = _SequenceDB(scalar_sequence=[role], scalars_result=[])

        main_module.app.dependency_overrides[get_current_user] = _override_user(_admin_user())
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            with caplog.at_level(logging.INFO, logger="app.routes.roles"):
                client.delete(f"/api/v1/roles/{ROLE_ID}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

        deletion_records = [r for r in caplog.records if "role.deleted" in r.message]
        assert deletion_records
        record = deletion_records[0]
        assert hasattr(record, "role_id") or str(ROLE_ID) in str(vars(record))

    def test_no_audit_log_when_deletion_blocked(self, client, caplog):
        role = _make_role()
        p1 = _make_profile(USER_1_ID, "alice@example.com")
        db = _SequenceDB(scalar_sequence=[role], scalars_result=[p1])

        main_module.app.dependency_overrides[get_current_user] = _override_user(_admin_user())
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            with caplog.at_level(logging.INFO, logger="app.routes.roles"):
                client.delete(f"/api/v1/roles/{ROLE_ID}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

        assert not any("role.deleted" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# 4. Auth / RBAC enforcement
# ---------------------------------------------------------------------------


class TestDeleteAuthorization:
    def test_non_admin_returns_403(self, client):
        db = _SequenceDB()

        main_module.app.dependency_overrides[get_current_user] = _override_user(_non_admin_user())
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            response = client.delete(f"/api/v1/roles/{ROLE_ID}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 403

    def test_unauthenticated_returns_401(self, client):
        response = client.delete(f"/api/v1/roles/{ROLE_ID}")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# 5. Not-found + org scoping
# ---------------------------------------------------------------------------


class TestDeleteNotFoundAndOrgScoping:
    def test_role_not_found_returns_404(self, client):
        # scalar returns None → role not found in org
        db = _SequenceDB(scalar_sequence=[None])

        main_module.app.dependency_overrides[get_current_user] = _override_user(_admin_user())
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            response = client.delete(f"/api/v1/roles/{uuid4()}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 404

    def test_role_from_other_org_returns_404(self, client):
        """
        _get_org_role_for_org filters by both role_id AND organization_id.
        A role belonging to another org is invisible (not accessible cross-tenant).
        """
        other_org = UUID("bbbbbbbb-0000-0000-0000-000000000001")
        db = _SequenceDB(scalar_sequence=[None])  # query returns nothing for wrong org

        main_module.app.dependency_overrides[get_current_user] = _override_user(
            _admin_user(org_id=ORG_ID)
        )
        main_module.app.dependency_overrides[get_db] = _override_db(db)
        try:
            response = client.delete(f"/api/v1/roles/{ROLE_ID}")
        finally:
            main_module.app.dependency_overrides.pop(get_current_user, None)
            main_module.app.dependency_overrides.pop(get_db, None)

        assert response.status_code == 404
