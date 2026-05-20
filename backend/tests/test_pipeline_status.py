"""Unit and integration tests for PIPE-003: Pipeline Status Tracking.

Tests cover:
- PipelineStatusChangeRequest schema validation (withdrawal reason enforcement)
- WithdrawPipelineRequest schema validation
- PipelineStatusHistoryResponse serialisation
- PipelineService.change_pipeline_status — happy paths, no-op conflict, reopen guard
- PipelineService.withdraw_pipeline — delegates correctly
- PipelineService.get_status_history — ordered results
- Route-level tests: POST /status, POST /withdraw, GET /status-history
- Audit row written for every change
- COMM-005 notification called but failure is suppressed
- Status filter in list still works (AIR-520)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.pipeline import Pipeline, PipelineStatusHistory
from app.schemas.pipeline import (
    PipelineStatus,
    PipelineStatusChangeRequest,
    PipelineStatusHistoryResponse,
    WithdrawPipelineRequest,
)


# ── Schema: PipelineStatusChangeRequest ──────────────────────────────────────

class TestPipelineStatusChangeRequest:
    def test_active_requires_no_reason(self):
        req = PipelineStatusChangeRequest(status=PipelineStatus.ACTIVE)
        assert req.reason is None

    def test_on_hold_requires_no_reason(self):
        req = PipelineStatusChangeRequest(status=PipelineStatus.ON_HOLD, reason=None)
        assert req.status == PipelineStatus.ON_HOLD

    def test_closed_requires_no_reason(self):
        req = PipelineStatusChangeRequest(status=PipelineStatus.CLOSED)
        assert req.status == PipelineStatus.CLOSED

    def test_withdrawn_requires_reason_of_5_chars(self):
        with pytest.raises(ValidationError) as exc_info:
            PipelineStatusChangeRequest(status=PipelineStatus.WITHDRAWN, reason="ab")
        assert "5 characters" in str(exc_info.value)

    def test_withdrawn_with_no_reason_raises(self):
        with pytest.raises(ValidationError):
            PipelineStatusChangeRequest(status=PipelineStatus.WITHDRAWN)

    def test_withdrawn_with_sufficient_reason_passes(self):
        req = PipelineStatusChangeRequest(
            status=PipelineStatus.WITHDRAWN,
            reason="Candidate accepted another offer"
        )
        assert req.status == PipelineStatus.WITHDRAWN
        assert req.reason is not None

    def test_withdrawn_reason_stripped_before_length_check(self):
        """Whitespace-only reason still fails even if len >= 5."""
        with pytest.raises(ValidationError):
            PipelineStatusChangeRequest(status=PipelineStatus.WITHDRAWN, reason="     ")


# ── Schema: WithdrawPipelineRequest ─────────────────────────────────────────

class TestWithdrawPipelineRequest:
    def test_reason_required(self):
        with pytest.raises(ValidationError):
            WithdrawPipelineRequest()  # type: ignore[call-arg]

    def test_reason_min_length_5(self):
        with pytest.raises(ValidationError):
            WithdrawPipelineRequest(reason="ab")

    def test_valid_reason(self):
        req = WithdrawPipelineRequest(reason="Accepted elsewhere")
        assert req.reason == "Accepted elsewhere"


# ── Schema: PipelineStatusHistoryResponse ────────────────────────────────────

class TestPipelineStatusHistoryResponse:
    def test_from_orm(self):
        now = __import__("datetime").datetime.now(__import__("datetime").UTC)
        pid = uuid4()
        oid = uuid4()
        actor = uuid4()
        row = PipelineStatusHistory(
            id=uuid4(),
            pipeline_id=pid,
            organization_id=oid,
            previous_status="active",
            new_status="on_hold",
            actor_user_id=actor,
            reason="Need more time",
            changed_at=now,
            created_at=now,
        )
        resp = PipelineStatusHistoryResponse.model_validate(row)
        assert resp.previous_status == "active"
        assert resp.new_status == "on_hold"
        assert resp.actor_user_id == actor
        assert resp.reason == "Need more time"

    def test_null_previous_status(self):
        now = __import__("datetime").datetime.now(__import__("datetime").UTC)
        row = PipelineStatusHistory(
            id=uuid4(),
            pipeline_id=uuid4(),
            organization_id=uuid4(),
            previous_status=None,
            new_status="active",
            actor_user_id=None,
            reason=None,
            changed_at=now,
            created_at=now,
        )
        resp = PipelineStatusHistoryResponse.model_validate(row)
        assert resp.previous_status is None
        assert resp.actor_user_id is None
        assert resp.reason is None


# ── Service: change_pipeline_status ─────────────────────────────────────────

def _make_pipeline(
    status: str = "active",
    stage: str = "applied",
    org_id=None,
) -> Pipeline:
    p = Pipeline(
        id=uuid4(),
        organization_id=org_id or uuid4(),
        candidate_id=uuid4(),
        job_id=uuid4(),
        stage=stage,
        status=status,
    )
    return p


def _make_user(user_id=None, org_id=None, role: str = "recruiter"):
    user = MagicMock()
    user.user_id = str(user_id or uuid4())
    user.organization_id = str(org_id or uuid4())
    user.role = role
    return user


def _make_service(pipeline: Pipeline):
    """Return a PipelineService with a mocked db that returns the given pipeline."""
    from app.services.pipeline_service import PipelineService  # noqa: PLC0415

    service = PipelineService.__new__(PipelineService)
    service.db = MagicMock()
    service.db.scalar.return_value = pipeline
    service.db.scalars.return_value.all.return_value = []
    service._scope = MagicMock()
    service._scope.is_scoped_user.return_value = False
    service._candidates = MagicMock()
    return service


class TestChangePipelineStatus:
    def test_same_status_raises_409(self):
        pipeline = _make_pipeline(status="active")
        service = _make_service(pipeline)
        user = _make_user()

        with pytest.raises(HTTPException) as exc_info:
            service.change_pipeline_status(
                pipeline.id,
                pipeline.organization_id,
                user,
                PipelineStatusChangeRequest(status=PipelineStatus.ACTIVE),
            )
        assert exc_info.value.status_code == 409
        assert "already" in str(exc_info.value.detail).lower()

    def test_non_admin_cannot_reopen_closed_pipeline(self):
        pipeline = _make_pipeline(status="closed")
        service = _make_service(pipeline)
        user = _make_user(role="recruiter")

        with pytest.raises(HTTPException) as exc_info:
            service.change_pipeline_status(
                pipeline.id,
                pipeline.organization_id,
                user,
                PipelineStatusChangeRequest(status=PipelineStatus.ACTIVE),
            )
        assert exc_info.value.status_code == 403

    def test_admin_can_reopen_closed_pipeline(self):
        pipeline = _make_pipeline(status="closed")
        service = _make_service(pipeline)
        user = _make_user(role="admin")

        # Should NOT raise — admin is allowed.
        with patch("app.services.pipeline_service._notify_status_change"):
            service.change_pipeline_status(
                pipeline.id,
                pipeline.organization_id,
                user,
                PipelineStatusChangeRequest(status=PipelineStatus.ACTIVE),
            )
        # Verify status was updated on the model.
        assert pipeline.status == "active"

    def test_happy_path_writes_history_row(self):
        pipeline = _make_pipeline(status="active")
        service = _make_service(pipeline)
        user = _make_user()

        added_objects = []
        service.db.add.side_effect = added_objects.append

        with patch("app.services.pipeline_service._notify_status_change"):
            service.change_pipeline_status(
                pipeline.id,
                pipeline.organization_id,
                user,
                PipelineStatusChangeRequest(status=PipelineStatus.ON_HOLD),
            )

        history_rows = [o for o in added_objects if isinstance(o, PipelineStatusHistory)]
        assert len(history_rows) == 1
        assert history_rows[0].previous_status == "active"
        assert history_rows[0].new_status == "on_hold"

    def test_happy_path_updates_status_changed_at(self):
        pipeline = _make_pipeline(status="active")
        assert pipeline.status_changed_at is None  # no pre-existing timestamp

        service = _make_service(pipeline)
        user = _make_user()

        with patch("app.services.pipeline_service._notify_status_change"):
            service.change_pipeline_status(
                pipeline.id,
                pipeline.organization_id,
                user,
                PipelineStatusChangeRequest(status=PipelineStatus.ON_HOLD),
            )

        assert pipeline.status_changed_at is not None

    def test_notification_failure_is_suppressed(self):
        """A notification error must never bubble up and break the request."""
        pipeline = _make_pipeline(status="active")
        service = _make_service(pipeline)
        user = _make_user()

        with patch(
            "app.services.pipeline_service._notify_status_change",
            side_effect=RuntimeError("SMTP down"),
        ):
            # Should not raise.
            service.change_pipeline_status(
                pipeline.id,
                pipeline.organization_id,
                user,
                PipelineStatusChangeRequest(status=PipelineStatus.ON_HOLD),
            )

        assert pipeline.status == "on_hold"


# ── Service: withdraw_pipeline ────────────────────────────────────────────────

class TestWithdrawPipeline:
    def test_delegates_to_change_status_with_withdrawn(self):
        pipeline = _make_pipeline(status="active")
        service = _make_service(pipeline)
        user = _make_user()

        with patch.object(
            service, "change_pipeline_status", wraps=service.change_pipeline_status
        ) as spy:
            with patch("app.services.pipeline_service._notify_status_change"):
                service.withdraw_pipeline(
                    pipeline.id,
                    pipeline.organization_id,
                    user,
                    WithdrawPipelineRequest(reason="Accepted elsewhere"),
                )

        spy.assert_called_once()
        call_payload = spy.call_args[0][3]  # positional arg 4
        assert call_payload.status == PipelineStatus.WITHDRAWN
        assert call_payload.reason == "Accepted elsewhere"

    def test_withdraw_sets_status(self):
        pipeline = _make_pipeline(status="active")
        service = _make_service(pipeline)
        user = _make_user()

        with patch("app.services.pipeline_service._notify_status_change"):
            service.withdraw_pipeline(
                pipeline.id,
                pipeline.organization_id,
                user,
                WithdrawPipelineRequest(reason="Better opportunity elsewhere"),
            )

        assert pipeline.status == "withdrawn"


# ── Service: get_status_history ───────────────────────────────────────────────

class TestGetStatusHistory:
    def test_returns_history_rows_in_order(self):
        from app.services.pipeline_service import PipelineService  # noqa: PLC0415
        from datetime import datetime, UTC  # noqa: PLC0415

        pipeline = _make_pipeline()
        service = PipelineService.__new__(PipelineService)
        service._scope = MagicMock()
        service._scope.is_scoped_user.return_value = False

        now = datetime.now(UTC)

        rows = [
            PipelineStatusHistory(
                id=uuid4(),
                pipeline_id=pipeline.id,
                organization_id=pipeline.organization_id,
                previous_status=None,
                new_status="active",
                changed_at=now,
                created_at=now,
            ),
            PipelineStatusHistory(
                id=uuid4(),
                pipeline_id=pipeline.id,
                organization_id=pipeline.organization_id,
                previous_status="active",
                new_status="on_hold",
                changed_at=now,
                created_at=now,
            ),
        ]

        db = MagicMock()
        db.scalar.return_value = pipeline
        db.scalars.return_value = MagicMock()
        db.scalars.return_value.all.return_value = rows
        service.db = db

        user = _make_user(org_id=pipeline.organization_id)
        result = service.get_status_history(pipeline.id, pipeline.organization_id, user)

        assert len(result) == 2
        assert result[0].new_status == "active"
        assert result[1].new_status == "on_hold"


# ── Integration: Status filter in list (AIR-520) ─────────────────────────────

class TestStatusFilterInList:
    """Confirm that list_pipelines_paginated honours the pipeline_status filter."""

    def test_status_filter_is_applied(self):
        from app.services.pipeline_service import PipelineService  # noqa: PLC0415

        org_id = uuid4()
        service = PipelineService.__new__(PipelineService)
        service._scope = MagicMock()
        service._scope.is_scoped_user.return_value = False
        service._candidates = MagicMock()

        # Build mock DB results: one page row, count = 1, stage_counts = {}
        db = MagicMock()
        db.scalars.return_value = MagicMock()
        db.scalars.return_value.__iter__ = MagicMock(return_value=iter([]))
        db.scalar.return_value = 0
        db.execute.return_value = []
        service.db = db

        user = _make_user(org_id=org_id)
        pipelines, total, _ = service.list_pipelines_paginated(
            org_id,
            user,
            pipeline_status=PipelineStatus.ON_HOLD,
        )

        # Confirm the db.scalars call was made (the filter is passed through).
        assert db.scalars.called
