"""AIR-570/572: Automated pipeline stage email notifications."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.pipeline_stage_notification_service import (
    _pipeline_email_idempotency_key,
    _send_pipeline_stage_email,
)


def test_idempotency_key_stable():
    hid = str(uuid4())
    assert _pipeline_email_idempotency_key(hid) == f"ps-email-{hid}"


def test_skips_when_no_candidate_email():
    db = MagicMock()
    db.scalar.return_value = MagicMock(email=None, full_name="Test", first_name="Test")
    with patch(
        "app.services.pipeline_stage_notification_service.normalize_stage_for_pipeline_email",
        return_value="screening",
    ):
        _send_pipeline_stage_email(
            db=db,
            organization_id=uuid4(),
            org_id=uuid4(),
            workspace_id=uuid4(),
            candidate_id=uuid4(),
            pipeline_id=uuid4(),
            job_id=None,
            previous_stage="applied",
            new_stage="screening",
            stage_history_id=uuid4(),
            actor_user_id=uuid4(),
        )
    db.scalar.assert_called_once()


def test_send_email_failure_does_not_raise():
    org_id = uuid4()
    workspace_id = uuid4()
    candidate_id = uuid4()
    pipeline_id = uuid4()
    stage_history_id = uuid4()
    actor_id = uuid4()

    cm_candidate = MagicMock(
        email="candidate@example.com",
        full_name="Candidate",
        first_name="Candidate",
    )
    db = MagicMock()
    db.scalar.side_effect = [cm_candidate, None]

    comm = MagicMock()
    comm.send_email.side_effect = HTTPException(status_code=502, detail="SMTP down")

    with (
        patch(
            "app.services.pipeline_stage_notification_service.normalize_stage_for_pipeline_email",
            return_value="screening",
        ),
        patch(
            "app.services.pipeline_stage_notification_service.get_pipeline_stage_email_template",
            return_value=MagicMock(
                stage_key="screening",
                subject="Application update: Screening",
                body="Hello",
                groq_enhanced=False,
            ),
        ),
        patch(
            "app.services.pipeline_stage_notification_service.CommunicationService",
            return_value=comm,
        ),
    ):
        _send_pipeline_stage_email(
            db=db,
            organization_id=org_id,
            org_id=org_id,
            workspace_id=workspace_id,
            candidate_id=candidate_id,
            pipeline_id=pipeline_id,
            job_id=None,
            previous_stage="applied",
            new_stage="screening",
            stage_history_id=stage_history_id,
            actor_user_id=actor_id,
        )

    comm.send_email.assert_called_once()
    call_kwargs = comm.send_email.call_args.kwargs
    assert call_kwargs["idempotency_key"] == _pipeline_email_idempotency_key(str(stage_history_id))
    assert call_kwargs["pipeline_stage_notification"]["automated"] is True
