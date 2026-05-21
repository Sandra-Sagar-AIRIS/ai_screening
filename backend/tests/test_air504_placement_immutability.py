"""AIR-504: Placement history immutability — unit and integration checks."""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.exceptions.placement_history import ImmutablePlacementHistoryError
from app.main import app
from app.models.candidate_placement_history import CandidatePlacementHistory
from app.services.placement_history_service import PlacementHistoryService

pytestmark_integration = pytest.mark.integration


# ── Unit tests (no database) ───────────────────────────────────────────────────


def test_placement_history_service_has_no_update_delete_methods():
    assert not PlacementHistoryService._MUTATION_METHOD_NAMES & PlacementHistoryService.public_method_names()


def test_placement_history_service_public_api_is_append_and_list_only():
    allowed = {
        "append_record",
        "record_pending_submission",
        "record_pipeline_stage",
        "record_terminal_stage",
        "list_for_candidate",
    }
    assert PlacementHistoryService.public_method_names() == allowed


def test_fastapi_candidate_placements_routes_are_get_only():
    mutation_methods = {"POST", "PUT", "PATCH", "DELETE"}
    placement_routes = [
        r
        for r in app.routes
        if getattr(r, "path", None)
        and "{candidate_id}" in r.path
        and r.path.endswith("/placements")
    ]
    assert placement_routes, "Expected GET /candidates/{candidate_id}/placements route"
    for route in placement_routes:
        methods = getattr(route, "methods", None) or set()
        assert methods == {"GET"}, f"Unexpected methods on {route.path}: {methods}"
        assert not methods & mutation_methods


def test_http_mutations_on_placements_return_method_not_allowed(client, force_auth):
    """No POST/PUT/PATCH/DELETE handler is registered for the placements path."""
    candidate_id = uuid4()
    url = f"/api/v1/candidates/{candidate_id}/placements"
    for verb in ("post", "put", "patch"):
        res = getattr(client, verb)(url, json={})
        assert res.status_code == 405, f"{verb.upper()} should not be allowed (got {res.status_code})"
    res = client.delete(url)
    assert res.status_code == 405


# ── Integration tests (database) ───────────────────────────────────────────────


@pytestmark_integration
def test_placement_history_orm_update_is_blocked(client, auth_headers, db_session):
    seed = uuid4().hex[:8]
    candidate_id = client.post(
        "/api/v1/candidates", headers=auth_headers, json={
            "first_name": "Imm",
            "last_name": f"Test{seed}",
            "email": f"imm.{seed}@example.com",
        },
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json={"name": f"Client {seed}", "email": f"c-{seed}@example.com"},
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json={
            "client_id": client_id,
            "title": f"Job {seed}",
            "description": "t",
            "status": "open",
        },
    ).json()["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )

    row = db_session.scalar(
        select(CandidatePlacementHistory).where(
            CandidatePlacementHistory.candidate_id == candidate_id,
        )
    )
    assert row is not None
    row.outcome = "placed"
    with pytest.raises(ImmutablePlacementHistoryError):
        db_session.commit()
    db_session.rollback()

    fresh = db_session.scalar(
        select(CandidatePlacementHistory).where(CandidatePlacementHistory.id == row.id)
    )
    assert fresh is not None
    assert fresh.outcome == "pending"


@pytestmark_integration
def test_placement_history_orm_delete_is_blocked(client, auth_headers, db_session):
    seed = uuid4().hex[:8]
    candidate_id = client.post(
        "/api/v1/candidates", headers=auth_headers, json={
            "first_name": "Del",
            "last_name": f"Test{seed}",
            "email": f"del.{seed}@example.com",
        },
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json={"name": f"Client {seed}", "email": f"c2-{seed}@example.com"},
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json={
            "client_id": client_id,
            "title": f"Job {seed}",
            "description": "t",
            "status": "open",
        },
    ).json()["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )

    row = db_session.scalar(
        select(CandidatePlacementHistory).where(
            CandidatePlacementHistory.candidate_id == candidate_id,
        )
    )
    assert row is not None
    db_session.delete(row)
    with pytest.raises(ImmutablePlacementHistoryError):
        db_session.commit()
    db_session.rollback()

    assert db_session.get(CandidatePlacementHistory, row.id) is not None
