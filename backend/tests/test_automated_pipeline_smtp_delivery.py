"""Regression: automated pipeline emails must accept provider=smtp."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.candidate_management.communication_service import CommunicationService


def test_select_email_delivery_accepts_smtp_provider():
    svc = CommunicationService(MagicMock())
    delivery, conn = svc._select_email_delivery(
        org_id=uuid4(),
        workspace_id=uuid4(),
        user_id=uuid4(),
        requested_provider="smtp",
    )
    assert delivery == "smtp"
    assert conn is None
