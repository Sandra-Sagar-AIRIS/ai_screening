"""Reproduce GET interactions response serialization (no live DB)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.encoders import jsonable_encoder

from app.candidate_management.api import _success
from app.candidate_management.schemas import ApiResponse, InteractionResponse

pytestmark = pytest.mark.unit


def test_api_response_list_interaction_serializes_for_json() -> None:
    ir = InteractionResponse(
        id=uuid4(),
        candidate_id=uuid4(),
        org_id=uuid4(),
        workspace_id=uuid4(),
        interaction_type="note",
        title=None,
        body=None,
        metadata={"k": 1},
        actor_user_id=None,
        actor_role=None,
        created_at=datetime.now(timezone.utc),
    )
    payload = _success([ir])
    assert isinstance(payload, ApiResponse)
    encoded = jsonable_encoder(payload)
    assert encoded["success"] is True
    assert len(encoded["data"]) == 1


def test_model_validate_from_orm_like_namespace() -> None:
    """ORM objects expose interaction_metadata, not metadata."""
    ns = SimpleNamespace(
        id=uuid4(),
        candidate_id=uuid4(),
        org_id=uuid4(),
        workspace_id=uuid4(),
        interaction_type="note",
        title=None,
        body=None,
        interaction_metadata={"x": 1},
        actor_user_id=None,
        actor_role=None,
        created_at=datetime.now(timezone.utc),
    )
    m = InteractionResponse.model_validate(ns)
    assert m.metadata == {"x": 1}
