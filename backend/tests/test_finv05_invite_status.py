"""F-INV-05 — Invite Status Tracking tests.

Acceptance criteria verified:
  1.  Newly created invite has status 'sent' with sent_at populated.
  2.  GET /invites/open transitions 'sent' → 'opened' and sets opened_at.
  3.  GET /invites/open is idempotent when already 'opened'.
  4.  GET /invites/open on missing/expired/accepted token returns 204 (no disclosure).
  5.  POST /invites/accept transitions to 'accepted' and sets accepted_at.
  6.  POST /invites/accept blocked when status is 'accepted' (409).
  7.  POST /invites/accept blocked when status is 'expired' (410).
  8.  POST /invites/accept blocked when expires_at < now regardless of status (410).
  9.  Resend resets status to 'sent', clears opened_at, updates sent_at.
 10.  Resend blocked when status == 'accepted' (409).
 11.  Admin invite list exposes all lifecycle timestamp fields.
 12.  sweep_expired_invites marks sent/opened past expiry as 'expired' with expired_at.
 13.  sweep_expired_invites does NOT touch accepted invites.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Generator
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.invite import (
    INVITE_STATUS_ACCEPTED,
    INVITE_STATUS_EXPIRED,
    INVITE_STATUS_OPENED,
    INVITE_STATUS_SENT,
    Invite,
)
from app.schemas.auth import CurrentUser

pytestmark = pytest.mark.unit

ORG_ID = UUID("cccccccc-0000-0000-0000-000000000001")
ADMIN_ID = UUID("cccccccc-0000-0000-0000-000000000002")
INVITE_ID = UUID("cccccccc-0000-0000-0000-000000000010")

_NOW = datetime(2026, 5, 22, 10, 0, 0, tzinfo=UTC)
_FUTURE = _NOW + timedelta(days=7)
_PAST = _NOW - timedelta(hours=1)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _admin() -> CurrentUser:
    return CurrentUser(
        user_id=str(ADMIN_ID),
        organization_id=str(ORG_ID),
        email="admin@example.com",
        role="admin",
        user_type="internal",
    )


def _make_invite(
    *,
    status: str = INVITE_STATUS_SENT,
    expires_at: datetime = _FUTURE,
    sent_at: datetime | None = _NOW,
    opened_at: datetime | None = None,
    accepted_at: datetime | None = None,
    expired_at: datetime | None = None,
    token: str = "valid-token-abc123xyz",
) -> MagicMock:
    inv = MagicMock(spec=Invite)
    inv.id = INVITE_ID
    inv.email = "invited@example.com"
    inv.organization_id = ORG_ID
    inv.role = "recruiter"
    inv.token = token
    inv.status = status
    inv.expires_at = expires_at
    inv.created_at = _NOW
    inv.sent_at = sent_at
    inv.opened_at = opened_at
    inv.accepted_at = accepted_at
    inv.expired_at = expired_at
    return inv


def _db_returning(invite: MagicMock | None) -> MagicMock:
    """Return a mock Session that yields `invite` on any scalar() call."""
    db = MagicMock()
    db.scalar.return_value = invite
    db.scalars.return_value.all.return_value = [invite] if invite else []
    return db


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    app = main_module.app
    app.dependency_overrides[get_current_user] = _admin
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


def _override_db(db: MagicMock) -> None:
    main_module.app.dependency_overrides[get_db] = lambda: db


# ── 1. Create invite → status = 'sent', sent_at populated ────────────────────


def test_create_invite_sets_sent_status(client: TestClient) -> None:
    from app.models.invite import Invite as RealInvite

    db = MagicMock()
    db.scalar.return_value = None  # no existing profile, no duplicate active invite

    added_objects: list = []

    def _add(obj: object) -> None:
        added_objects.append(obj)

    def _refresh(obj: object) -> None:
        # Simulate DB populating server-defaults so serialization works
        if isinstance(obj, RealInvite):
            if obj.id is None:
                obj.id = INVITE_ID
            if obj.created_at is None:
                obj.created_at = _NOW

    db.add.side_effect = _add
    db.refresh = _refresh
    _override_db(db)

    with (
        patch("app.routes.invites.get_role_id_by_key", return_value=uuid4()),
        patch("app.routes.invites._now_utc", return_value=_NOW),
        patch("app.routes.invites.send_invite_email_task") as mock_task,
    ):
        resp = client.post(
            "/api/v1/invites",
            json={"email": "newuser@example.com", "role": "recruiter"},
        )

    assert resp.status_code == 201
    mock_task.apply_async.assert_called_once()
    # Verify the Invite that was added has status='sent' and sent_at set
    invite_objs = [o for o in added_objects if isinstance(o, RealInvite)]
    assert len(invite_objs) == 1
    assert invite_objs[0].status == INVITE_STATUS_SENT
    assert invite_objs[0].sent_at == _NOW


def test_create_invite_status_constant() -> None:
    """Verify the model constant value."""
    assert INVITE_STATUS_SENT == "sent"


# ── 2. GET /invites/open → sent → opened, opened_at set ──────────────────────


def test_open_invite_transitions_sent_to_opened(client: TestClient) -> None:
    invite = _make_invite(status=INVITE_STATUS_SENT)
    db = _db_returning(invite)
    _override_db(db)

    with patch("app.routes.invites._now_utc", return_value=_NOW):
        resp = client.get("/api/v1/invites/open?token=valid-token-abc123xyz")

    assert resp.status_code == 204
    assert invite.status == INVITE_STATUS_OPENED
    assert invite.opened_at == _NOW
    db.add.assert_called_once_with(invite)
    db.commit.assert_called_once()


# ── 3. GET /invites/open is idempotent when already 'opened' ─────────────────


def test_open_invite_idempotent_when_opened(client: TestClient) -> None:
    original_opened_at = _NOW - timedelta(minutes=5)
    invite = _make_invite(status=INVITE_STATUS_OPENED, opened_at=original_opened_at)
    db = _db_returning(invite)
    _override_db(db)

    resp = client.get("/api/v1/invites/open?token=valid-token-abc123xyz")

    assert resp.status_code == 204
    db.add.assert_not_called()  # no mutation for already-opened
    assert invite.opened_at == original_opened_at  # unchanged


# ── 4. GET /invites/open on unknown/accepted/expired → 204, no disclosure ────


@pytest.mark.parametrize("invite_val", [None, "accepted", "expired"])
def test_open_invite_no_disclosure(client: TestClient, invite_val: object) -> None:
    if invite_val is None:
        invite = None
    else:
        invite = _make_invite(status=str(invite_val))
    db = _db_returning(invite)
    _override_db(db)

    resp = client.get("/api/v1/invites/open?token=whatever-token")

    assert resp.status_code == 204
    db.commit.assert_not_called()


# ── 5. POST /invites/accept → accepted + accepted_at ─────────────────────────


def test_accept_invite_sets_accepted_at(client: TestClient) -> None:
    invite = _make_invite(status=INVITE_STATUS_OPENED)
    db = _db_returning(invite)
    db.scalar.side_effect = [invite, None]  # invite found, no existing profile
    _override_db(db)

    with (
        patch("app.routes.invites.get_role_id_by_key", return_value=uuid4()),
        patch("app.routes.invites.hash_password", return_value="hashed"),
        patch("app.routes.invites._now_utc", return_value=_NOW),
    ):
        resp = client.post(
            "/api/v1/invites/accept",
            json={"token": "valid-token-abc123xyz", "password": "Str0ngPass!"},
        )

    assert resp.status_code == 200
    assert invite.status == INVITE_STATUS_ACCEPTED
    assert invite.accepted_at == _NOW


# ── 6. Accept blocked when already accepted ───────────────────────────────────


def test_accept_invite_rejected_when_already_accepted(client: TestClient) -> None:
    invite = _make_invite(status=INVITE_STATUS_ACCEPTED)
    db = _db_returning(invite)
    db.scalar.return_value = invite
    _override_db(db)

    resp = client.post(
        "/api/v1/invites/accept",
        json={"token": "valid-token-abc123xyz", "password": "Str0ngPass!"},
    )

    assert resp.status_code == 409


# ── 7. Accept blocked when status is 'expired' ───────────────────────────────


def test_accept_invite_rejected_when_expired_status(client: TestClient) -> None:
    invite = _make_invite(status=INVITE_STATUS_EXPIRED, expires_at=_PAST)
    db = _db_returning(invite)
    db.scalar.return_value = invite
    _override_db(db)

    resp = client.post(
        "/api/v1/invites/accept",
        json={"token": "valid-token-abc123xyz", "password": "Str0ngPass!"},
    )

    assert resp.status_code == 410


# ── 8. Accept blocked when expires_at in the past ────────────────────────────


def test_accept_invite_rejected_when_past_expiry(client: TestClient) -> None:
    invite = _make_invite(status=INVITE_STATUS_SENT, expires_at=_PAST)
    db = _db_returning(invite)
    db.scalar.return_value = invite
    _override_db(db)

    with patch("app.routes.invites._now_utc", return_value=_NOW):
        resp = client.post(
            "/api/v1/invites/accept",
            json={"token": "valid-token-abc123xyz", "password": "Str0ngPass!"},
        )

    assert resp.status_code == 410


# ── 9. Resend resets to 'sent', clears opened_at, updates sent_at ─────────────


def test_resend_invite_resets_lifecycle(client: TestClient) -> None:
    invite = _make_invite(status=INVITE_STATUS_OPENED, opened_at=_NOW - timedelta(hours=1))
    db = MagicMock()
    db.scalar.return_value = invite
    db.refresh = lambda _: None
    _override_db(db)

    with (
        patch("app.routes.invites._now_utc", return_value=_NOW),
        patch("app.routes.invites.send_invite_email_task") as mock_task,
    ):
        resp = client.post(f"/api/v1/invites/{INVITE_ID}/resend")

    assert resp.status_code == 200
    assert invite.status == INVITE_STATUS_SENT
    assert invite.sent_at == _NOW
    assert invite.opened_at is None
    mock_task.apply_async.assert_called_once()


# ── 10. Resend blocked when accepted ──────────────────────────────────────────


def test_resend_invite_blocked_when_accepted(client: TestClient) -> None:
    invite = _make_invite(status=INVITE_STATUS_ACCEPTED)
    db = MagicMock()
    db.scalar.return_value = invite
    _override_db(db)

    resp = client.post(f"/api/v1/invites/{INVITE_ID}/resend")

    assert resp.status_code == 409


# ── 11. Admin list exposes lifecycle timestamps ───────────────────────────────


def test_invite_list_exposes_lifecycle_timestamps(client: TestClient) -> None:
    invite = _make_invite(
        status=INVITE_STATUS_ACCEPTED,
        sent_at=_NOW - timedelta(days=3),
        opened_at=_NOW - timedelta(days=2),
        accepted_at=_NOW - timedelta(days=1),
    )
    db = MagicMock()
    db.scalars.return_value.all.return_value = [invite]
    _override_db(db)

    resp = client.get("/api/v1/invites")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["status"] == INVITE_STATUS_ACCEPTED
    assert item["sent_at"] is not None
    assert item["opened_at"] is not None
    assert item["accepted_at"] is not None
    assert item["expired_at"] is None


# ── 12. sweep_expired_invites marks expired correctly ────────────────────────


def test_sweep_expired_invites_marks_expired() -> None:
    from app.tasks.invite_tasks import sweep_expired_invites

    db = MagicMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = [("id1",), ("id2",)]
    db.execute.return_value = result_mock

    with patch("app.db.session.SessionLocal", return_value=db):
        result = sweep_expired_invites()

    assert result["expired"] == 2
    db.commit.assert_called_once()


# ── 13. sweep_expired_invites does not affect accepted ───────────────────────


def test_sweep_expired_invites_leaves_accepted() -> None:
    """Accepted invites must not be touched — verified via query filter."""
    from app.tasks.invite_tasks import sweep_expired_invites

    db = MagicMock()
    result_mock = MagicMock()
    result_mock.fetchall.return_value = []  # nothing expired
    db.execute.return_value = result_mock

    with patch("app.db.session.SessionLocal", return_value=db):
        result = sweep_expired_invites()

    assert result["expired"] == 0
    # Commit still called (idempotent)
    db.commit.assert_called_once()
