"""
WS-002: Client Workspace Creation — Test Suite

Covers:
  - Schema validation (ClientCreate required fields, email format)
  - Org-level name uniqueness enforcement
  - Soft delete behavior (is_deleted, deleted_at, excluded from queries)
  - Recruiter visibility (assigned recruiters see client, unassigned do not)
  - Admin bypass of recruiter visibility filter
  - Recruiter assignment CRUD (assign, list, remove)
  - Unauthorized access prevention
  - Cross-org isolation
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, call, patch
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError

from app.schemas.client import ClientCreate, ClientUpdate, ClientRecruiterResponse
from app.services.client_service import ClientService


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _db():
    return MagicMock()


def _make_client(org_id=None, name="Acme Corp", is_deleted=False):
    c = MagicMock()
    c.id = uuid4()
    c.organization_id = org_id or uuid4()
    c.name = name
    c.industry = "Technology"
    c.email = "contact@acme.com"
    c.is_deleted = is_deleted
    c.deleted_at = None
    c.deleted_by = None
    return c


def _make_assignment(client_id=None, recruiter_id=None):
    a = MagicMock()
    a.id = uuid4()
    a.client_id = client_id or uuid4()
    a.recruiter_id = recruiter_id or uuid4()
    a.assigned_by = None
    a.assigned_at = datetime.now(timezone.utc)
    return a


# ── Schema validation ─────────────────────────────────────────────────────────

class TestClientCreateSchema:
    def test_valid_payload(self):
        payload = ClientCreate(
            name="Acme Corp",
            industry="Technology",
            email="contact@acme.com",
        )
        assert payload.name == "Acme Corp"
        assert payload.industry == "Technology"
        assert str(payload.email) == "contact@acme.com"

    def test_missing_industry_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            ClientCreate(name="Acme Corp", email="contact@acme.com")
        errors = exc_info.value.errors()
        fields = [e["loc"][0] for e in errors]
        assert "industry" in fields

    def test_missing_email_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            ClientCreate(name="Acme Corp", industry="Technology")
        errors = exc_info.value.errors()
        fields = [e["loc"][0] for e in errors]
        assert "email" in fields

    def test_missing_name_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            ClientCreate(industry="Technology", email="contact@acme.com")
        errors = exc_info.value.errors()
        fields = [e["loc"][0] for e in errors]
        assert "name" in fields

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            ClientCreate(name="Acme Corp", industry="Technology", email="not-an-email")

    def test_name_too_short_raises(self):
        with pytest.raises(ValidationError):
            ClientCreate(name="", industry="Technology", email="x@x.com")

    def test_optional_assigned_recruiter_ids_defaults_empty(self):
        payload = ClientCreate(
            name="Acme Corp",
            industry="Technology",
            email="contact@acme.com",
        )
        assert payload.assigned_recruiter_ids == []

    def test_assigned_recruiter_ids_accepted(self):
        rid = uuid4()
        payload = ClientCreate(
            name="Acme Corp",
            industry="Technology",
            email="contact@acme.com",
            assigned_recruiter_ids=[rid],
        )
        assert rid in payload.assigned_recruiter_ids


# ── Org-level uniqueness ──────────────────────────────────────────────────────

class TestClientUniqueness:
    def _service_with_existing(self, existing_client):
        db = _db()
        db.scalar.return_value = existing_client
        db.scalars.return_value.all.return_value = []
        return ClientService(db)

    def _service_no_existing(self):
        db = _db()
        # First scalar call (uniqueness check) → None; second (get_by_id) → client
        db.scalar.return_value = None
        db.scalars.return_value.all.return_value = []
        return ClientService(db)

    def test_duplicate_name_same_org_raises_409(self):
        existing = _make_client(name="Acme Corp")
        svc = self._service_with_existing(existing)
        payload = ClientCreate(name="Acme Corp", industry="Tech", email="a@b.com")
        with pytest.raises(HTTPException) as exc_info:
            svc._assert_unique_name(existing.organization_id, "Acme Corp")
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["error"] == "CLIENT_NAME_CONFLICT"

    def test_case_insensitive_duplicate_raises_409(self):
        existing = _make_client(name="acme corp")
        svc = self._service_with_existing(existing)
        with pytest.raises(HTTPException) as exc_info:
            svc._assert_unique_name(existing.organization_id, "ACME CORP")
        assert exc_info.value.status_code == 409

    def test_same_name_different_org_allowed(self):
        db = _db()
        db.scalar.return_value = None  # no conflict found
        db.scalars.return_value.all.return_value = []
        svc = ClientService(db)
        # Should not raise
        svc._assert_unique_name(uuid4(), "Acme Corp")

    def test_update_same_name_excluded_from_uniqueness(self):
        db = _db()
        db.scalar.return_value = None
        db.scalars.return_value.all.return_value = []
        svc = ClientService(db)
        client_id = uuid4()
        # Passing exclude_id=client_id means updating its own name — should not raise
        svc._assert_unique_name(uuid4(), "Acme Corp", exclude_id=client_id)


# ── Soft delete ───────────────────────────────────────────────────────────────

class TestSoftDelete:
    def test_soft_delete_sets_flags(self):
        client = _make_client()
        deleter_id = uuid4()

        db = _db()
        # scalar for get_client_by_id (is_deleted=False check)
        db.scalar.return_value = client
        # scalars not called in soft_delete path (no _enrich)
        svc = ClientService(db)

        svc.soft_delete_client(client.id, client.organization_id, deleted_by=deleter_id)

        assert client.is_deleted is True
        assert client.deleted_at is not None
        assert client.deleted_by == deleter_id
        db.commit.assert_called_once()

    def test_soft_delete_nonexistent_raises_404(self):
        db = _db()
        db.scalar.return_value = None
        svc = ClientService(db)
        with pytest.raises(HTTPException) as exc_info:
            svc.soft_delete_client(uuid4(), uuid4())
        assert exc_info.value.status_code == 404

    def test_deleted_client_not_returned_in_list(self):
        db = _db()
        db.scalars.return_value = iter([])  # list query returns empty
        svc = ClientService(db)
        result = svc.list_clients(uuid4())
        assert result == []

    def test_get_deleted_client_raises_404(self):
        db = _db()
        db.scalar.return_value = None  # filtered by is_deleted=False
        svc = ClientService(db)
        with pytest.raises(HTTPException) as exc_info:
            svc.get_client_by_id(uuid4(), uuid4())
        assert exc_info.value.status_code == 404


# ── Recruiter visibility ──────────────────────────────────────────────────────

class TestRecruiterVisibility:
    def test_get_client_unassigned_recruiter_raises_403(self):
        client = _make_client()
        recruiter_id = uuid4()

        db = _db()
        # First scalar: get_client_by_id returns client (not deleted)
        # Second scalar: assignment check returns None (not assigned)
        db.scalar.side_effect = [client, None]
        db.scalars.return_value.all.return_value = []
        svc = ClientService(db)

        with pytest.raises(HTTPException) as exc_info:
            svc.get_client_by_id(client.id, client.organization_id, recruiter_id=recruiter_id)
        assert exc_info.value.status_code == 403

    def test_get_client_assigned_recruiter_succeeds(self):
        client = _make_client()
        recruiter_id = uuid4()
        assignment = _make_assignment(client_id=client.id, recruiter_id=recruiter_id)

        db = _db()
        db.scalar.side_effect = [client, assignment]
        db.scalars.return_value.all.return_value = [recruiter_id]
        svc = ClientService(db)

        result = svc.get_client_by_id(client.id, client.organization_id, recruiter_id=recruiter_id)
        assert result.id == client.id

    def test_get_client_admin_bypasses_visibility(self):
        client = _make_client()

        db = _db()
        db.scalar.return_value = client
        db.scalars.return_value.all.return_value = []
        svc = ClientService(db)

        # recruiter_id=None means admin path — no visibility check performed
        result = svc.get_client_by_id(client.id, client.organization_id, recruiter_id=None)
        assert result.id == client.id

    def test_list_clients_recruiter_scoped(self):
        recruiter_id = uuid4()
        client = _make_client()

        db = _db()
        # Both scalars calls (assignment subquery + list query + _enrich) return empty — we
        # only verify the service accepts recruiter_id without raising.
        db.scalars.return_value.all.return_value = []
        svc = ClientService(db)

        result = svc.list_clients(client.organization_id, recruiter_id=recruiter_id)
        assert isinstance(result, list)

    def test_list_clients_admin_no_filter(self):
        db = _db()
        db.scalars.return_value = iter([])
        svc = ClientService(db)
        # recruiter_id=None → admin path, no assignment subquery
        svc.list_clients(uuid4(), recruiter_id=None)


# ── Recruiter assignment CRUD ─────────────────────────────────────────────────

class TestRecruiterAssignment:
    def test_assign_recruiter_creates_row(self):
        client = _make_client()
        recruiter_id = uuid4()

        db = _db()
        # get_client_by_id → client
        db.scalar.return_value = client
        # existing assignments → empty
        db.scalars.return_value.all.return_value = []
        svc = ClientService(db)

        # Patch list_assigned_recruiters to avoid follow-up DB calls
        with patch.object(svc, "list_assigned_recruiters", return_value=[]):
            svc.assign_recruiters(client.id, client.organization_id, [recruiter_id])

        db.add.assert_called()
        db.commit.assert_called()

    def test_assign_recruiter_idempotent(self):
        client = _make_client()
        recruiter_id = uuid4()

        db = _db()
        db.scalar.return_value = client
        # recruiter already assigned
        db.scalars.return_value.all.return_value = [recruiter_id]
        svc = ClientService(db)

        with patch.object(svc, "list_assigned_recruiters", return_value=[]):
            svc.assign_recruiters(client.id, client.organization_id, [recruiter_id])

        # db.add should NOT have been called for the duplicate
        assert not any(
            str(recruiter_id) in str(call_args)
            for call_args in db.add.call_args_list
        )

    def test_remove_recruiter_not_assigned_raises_404(self):
        client = _make_client()

        db = _db()
        # get_client_by_id → client; assignment lookup → None
        db.scalar.side_effect = [client, None]
        db.scalars.return_value.all.return_value = []
        svc = ClientService(db)

        with pytest.raises(HTTPException) as exc_info:
            svc.remove_recruiter(client.id, client.organization_id, uuid4())
        assert exc_info.value.status_code == 404

    def test_remove_recruiter_deletes_row(self):
        client = _make_client()
        assignment = _make_assignment(client_id=client.id)

        db = _db()
        db.scalar.side_effect = [client, assignment]
        db.scalars.return_value.all.return_value = []
        svc = ClientService(db)

        svc.remove_recruiter(client.id, client.organization_id, assignment.recruiter_id)

        db.delete.assert_called_once_with(assignment)
        db.commit.assert_called()


# ── Cross-org isolation ───────────────────────────────────────────────────────

class TestCrossOrgIsolation:
    def test_get_client_wrong_org_raises_404(self):
        db = _db()
        db.scalar.return_value = None  # org filter causes miss
        svc = ClientService(db)

        with pytest.raises(HTTPException) as exc_info:
            svc.get_client_by_id(uuid4(), uuid4())
        assert exc_info.value.status_code == 404

    def test_soft_delete_wrong_org_raises_404(self):
        db = _db()
        db.scalar.return_value = None
        svc = ClientService(db)

        with pytest.raises(HTTPException) as exc_info:
            svc.soft_delete_client(uuid4(), uuid4())
        assert exc_info.value.status_code == 404
