"""AIR-37: Candidate placement history — model, API, immutability, write hooks."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models.candidate_placement_history import CandidatePlacementHistory
from app.models.pipeline import Pipeline
from app.schemas.pipeline import PipelineStage, PipelineStageTransitionRequest

_STAGES_BEFORE_PLACED = (
    PipelineStage.SCREENING,
    PipelineStage.INTERVIEW,
    PipelineStage.OFFER,
)
from app.services.placement_history_service import PlacementHistoryService

pytestmark = pytest.mark.integration


def _create_client_payload(seed: str) -> dict:
    return {
        "name": f"Client {seed}",
        "legal_name": f"Client Legal {seed}",
        "industry": "Technology",
    }


def _create_job_payload(*, client_id: UUID, title: str, status: str = "open") -> dict:
    return {
        "client_id": str(client_id),
        "title": title,
        "description": "Test job",
        "status": status,
    }


def _create_candidate_payload(seed: str) -> dict:
    return {
        "first_name": "Place",
        "last_name": f"History{seed}",
        "email": f"place.history.{seed}@example.com",
    }


def test_submit_creates_pending_placement_history(client, auth_headers, db_session):
    seed = uuid4().hex[:8]
    candidate_id = client.post(
        "/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(seed)
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=f"Role {seed}"),
    ).json()["id"]

    res = client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )
    assert res.status_code == 201

    rows = list(
        db_session.scalars(
            select(CandidatePlacementHistory).where(
                CandidatePlacementHistory.candidate_id == UUID(candidate_id),
                CandidatePlacementHistory.job_id == UUID(job_id),
            )
        )
    )
    assert len(rows) == 1
    assert rows[0].outcome == "pending"


def test_transition_to_placed_appends_placement_history(client, auth_headers, db_session):
    seed = uuid4().hex[:8]
    candidate_id = client.post(
        "/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(seed)
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=f"Role {seed}"),
    ).json()["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )
    pipeline = db_session.scalar(
        select(Pipeline).where(
            Pipeline.candidate_id == UUID(candidate_id),
            Pipeline.job_id == UUID(job_id),
        )
    )
    assert pipeline is not None

    for stage in _STAGES_BEFORE_PLACED:
        r = client.post(
            f"/api/v1/pipelines/{pipeline.id}/transition",
            headers=auth_headers,
            json=PipelineStageTransitionRequest(stage=stage).model_dump(mode="json"),
        )
        assert r.status_code == 200, r.text

    r = client.post(
        f"/api/v1/pipelines/{pipeline.id}/transition",
        headers=auth_headers,
        json=PipelineStageTransitionRequest(stage=PipelineStage.PLACED).model_dump(mode="json"),
    )
    assert r.status_code == 200

    rows = list(
        db_session.scalars(
            select(CandidatePlacementHistory)
            .where(
                CandidatePlacementHistory.candidate_id == UUID(candidate_id),
                CandidatePlacementHistory.job_id == UUID(job_id),
            )
            .order_by(CandidatePlacementHistory.placement_date)
        )
    )
    assert len(rows) == 5
    assert rows[0].outcome == "pending"
    assert [r.outcome for r in rows[1:]] == ["screening", "interview", "offer", "placed"]


def test_pipeline_stage_timeline_skips_duplicate_consecutive_stage(client, auth_headers, db_session):
    """Same stage transition twice does not append duplicate placement rows."""
    seed = uuid4().hex[:8]
    candidate_id = client.post(
        "/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(seed)
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=f"Dup {seed}"),
    ).json()["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )
    pipeline = db_session.scalar(
        select(Pipeline).where(
            Pipeline.candidate_id == UUID(candidate_id),
            Pipeline.job_id == UUID(job_id),
        )
    )
    assert pipeline is not None
    svc = PlacementHistoryService(db_session)
    svc.record_pipeline_stage(
        candidate_id=UUID(candidate_id),
        job_id=UUID(job_id),
        stage=PipelineStage.SCREENING.value,
    )
    svc.record_pipeline_stage(
        candidate_id=UUID(candidate_id),
        job_id=UUID(job_id),
        stage=PipelineStage.SCREENING.value,
    )
    db_session.commit()
    rows = list(
        db_session.scalars(
            select(CandidatePlacementHistory)
            .where(
                CandidatePlacementHistory.candidate_id == UUID(candidate_id),
                CandidatePlacementHistory.job_id == UUID(job_id),
            )
            .order_by(CandidatePlacementHistory.placement_date)
        )
    )
    outcomes = [r.outcome for r in rows]
    assert outcomes.count("screening") == 1


def test_get_candidate_placements_returns_full_timeline_newest_first(client, auth_headers, db_session):
    """AIR-503: API returns all stage rows; newest outcome first for a job."""
    seed = uuid4().hex[:8]
    candidate_id = client.post(
        "/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(seed)
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=f"Hired {seed}"),
    ).json()["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )
    pipeline = db_session.scalar(
        select(Pipeline).where(
            Pipeline.candidate_id == UUID(candidate_id),
            Pipeline.job_id == UUID(job_id),
        )
    )
    for stage in _STAGES_BEFORE_PLACED:
        client.post(
            f"/api/v1/pipelines/{pipeline.id}/transition",
            headers=auth_headers,
            json=PipelineStageTransitionRequest(stage=stage).model_dump(mode="json"),
        )
    client.post(
        f"/api/v1/pipelines/{pipeline.id}/transition",
        headers=auth_headers,
        json=PipelineStageTransitionRequest(stage=PipelineStage.PLACED).model_dump(mode="json"),
    )

    res = client.get(f"/api/v1/candidates/{candidate_id}/placements", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 5
    assert data[0]["outcome"] == "placed"
    assert "placement_date" in data[0]
    assert data[0]["job_title"] == f"Hired {seed}"
    assert {row["outcome"] for row in data} == {
        "pending",
        "screening",
        "interview",
        "offer",
        "placed",
    }


def test_get_candidate_placements_sorted_latest_first(client, auth_headers, db_session):
    """AIR-503: Multiple jobs ordered by most recent placement_date descending."""
    seed = uuid4().hex[:8]
    candidate_id = client.post(
        "/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(seed)
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)
    ).json()["id"]

    job_old = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=f"Older {seed}"),
    ).json()["id"]
    job_new = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=f"Newer {seed}"),
    ).json()["id"]

    client.post(
        f"/api/v1/jobs/{job_old}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )
    client.post(
        f"/api/v1/jobs/{job_new}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )

    res = client.get(f"/api/v1/candidates/{candidate_id}/placements", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert len(data) == 2
    assert data[0]["job_title"] == f"Newer {seed}"
    assert data[1]["job_title"] == f"Older {seed}"
    dates = [row["placement_date"] for row in data]
    assert dates[0] >= dates[1]


def test_get_candidate_placements_filters_by_candidate_id(client, auth_headers, db_session):
    """AIR-503: Other candidates' placement rows are not returned."""
    seed = uuid4().hex[:8]
    cand_a = client.post(
        "/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(f"a{seed}")
    ).json()["id"]
    cand_b = client.post(
        "/api/v1/candidates",
        headers=auth_headers,
        json={
            "first_name": "Other",
            "last_name": f"User{seed}",
            "email": f"other.{seed}@example.com",
        },
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=f"Only A {seed}"),
    ).json()["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": cand_a, "notes": None},
    )

    res = client.get(f"/api/v1/candidates/{cand_b}/placements", headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["total"] == 0
    assert res.json()["data"] == []


def test_get_candidate_placements_not_found_for_unknown_candidate(client, auth_headers):
    missing = uuid4()
    res = client.get(f"/api/v1/candidates/{missing}/placements", headers=auth_headers)
    assert res.status_code == 404


def test_get_candidate_placements_api(client, auth_headers, db_session):
    seed = uuid4().hex[:8]
    candidate_id = client.post(
        "/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(seed)
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)
    ).json()["id"]
    job_title = f"Placement API {seed}"
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=job_title),
    ).json()["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )

    res = client.get(f"/api/v1/candidates/{candidate_id}/placements", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert len(body["data"]) == 1
    row = body["data"][0]
    assert row["job_title"] == job_title
    assert row["outcome"] == "pending"
    assert row["job_id"] == job_id


def test_get_candidate_placements_includes_rejection_reason(client, auth_headers, db_session):
    seed = uuid4().hex[:8]
    candidate_id = client.post(
        "/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(seed)
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=f"Reject {seed}"),
    ).json()["id"]
    client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )
    pipeline = db_session.scalar(
        select(Pipeline).where(
            Pipeline.candidate_id == UUID(candidate_id),
            Pipeline.job_id == UUID(job_id),
        )
    )
    assert pipeline is not None
    reason_text = "Candidate lacks required React experience for this role."
    client.post(
        f"/api/v1/pipelines/{pipeline.id}/transition",
        headers=auth_headers,
        json=PipelineStageTransitionRequest(
            stage=PipelineStage.REJECTED,
            reason=reason_text,
        ).model_dump(mode="json"),
    )

    res = client.get(f"/api/v1/candidates/{candidate_id}/placements", headers=auth_headers)
    assert res.status_code == 200
    row = res.json()["data"][0]
    assert row["outcome"] == "rejected"
    assert row["rejection_reason"] == reason_text


def test_placement_history_service_has_no_update_delete():
    """AIR-504: covered in test_air504_placement_immutability.py (kept for backwards compatibility)."""
    assert not PlacementHistoryService._MUTATION_METHOD_NAMES & PlacementHistoryService.public_method_names()
