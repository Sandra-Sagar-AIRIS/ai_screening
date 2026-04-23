from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.interview import Interview
from app.models.pipeline import Pipeline

pytestmark = pytest.mark.integration


def _create_candidate_payload(seed: str) -> dict[str, str]:
    return {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": f"jane-{seed}@example.com",
    }


def _create_client_payload(seed: str) -> dict[str, str]:
    return {
        "name": f"Acme {seed}",
        "email": f"client-{seed}@example.com",
    }


def test_pipeline_uniqueness_constraint_returns_409(client, auth_headers):
    seed = uuid4().hex[:8]
    candidate_res = client.post("/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(seed))
    assert candidate_res.status_code == 201
    candidate_id = candidate_res.json()["id"]

    client_res = client.post("/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed))
    assert client_res.status_code == 201
    client_id = client_res.json()["id"]

    job_res = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json={"client_id": client_id, "title": f"Backend Engineer {seed}", "status": "open"},
    )
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    first_pipeline = client.post(
        "/api/v1/pipelines",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "job_id": job_id, "stage": "applied", "status": "active"},
    )
    assert first_pipeline.status_code == 201

    duplicate_pipeline = client.post(
        "/api/v1/pipelines",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "job_id": job_id, "stage": "screening", "status": "active"},
    )
    assert duplicate_pipeline.status_code == 409


def test_invalid_pipeline_foreign_keys_return_404(client, auth_headers):
    response = client.post(
        "/api/v1/pipelines",
        headers=auth_headers,
        json={
            "candidate_id": str(uuid4()),
            "job_id": str(uuid4()),
            "stage": "applied",
            "status": "active",
        },
    )
    assert response.status_code in {400, 404}


def test_failed_pipeline_request_rolls_back_without_partial_data(client, auth_headers, db_session: Session):
    seed = uuid4().hex[:8]
    candidate_id = client.post(
        "/api/v1/candidates",
        headers=auth_headers,
        json=_create_candidate_payload(seed),
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json=_create_client_payload(seed),
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json={"client_id": client_id, "title": f"Platform Engineer {seed}", "status": "open"},
    ).json()["id"]

    created = client.post(
        "/api/v1/pipelines",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "job_id": job_id, "stage": "applied", "status": "active"},
    )
    assert created.status_code == 201

    failed = client.post(
        "/api/v1/pipelines",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "job_id": job_id, "stage": "offer", "status": "active"},
    )
    assert failed.status_code == 409

    count_stmt = select(Pipeline).where(Pipeline.candidate_id == UUID(candidate_id), Pipeline.job_id == UUID(job_id))
    rows = list(db_session.scalars(count_stmt))
    assert len(rows) == 1


def test_relationship_chain_and_interview_pipeline_integrity(client, auth_headers, db_session: Session):
    seed = uuid4().hex[:8]
    candidate_id = client.post(
        "/api/v1/candidates",
        headers=auth_headers,
        json=_create_candidate_payload(seed),
    ).json()["id"]
    client_id = client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json=_create_client_payload(seed),
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json={"client_id": client_id, "title": f"Data Engineer {seed}", "status": "open"},
    ).json()["id"]
    pipeline_res = client.post(
        "/api/v1/pipelines",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "job_id": job_id, "stage": "interview", "status": "active"},
    )
    assert pipeline_res.status_code == 201
    pipeline_id = pipeline_res.json()["id"]

    interview_time = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    interview_res = client.post(
        "/api/v1/interviews",
        headers=auth_headers,
        json={"pipeline_id": pipeline_id, "scheduled_at": interview_time, "status": "scheduled"},
    )
    assert interview_res.status_code == 201
    interview_id = interview_res.json()["id"]

    interview_model = db_session.get(Interview, interview_id)
    assert interview_model is not None
    assert str(interview_model.pipeline_id) == pipeline_id

    invalid_interview = client.post(
        "/api/v1/interviews",
        headers=auth_headers,
        json={
            "pipeline_id": str(uuid4()),
            "scheduled_at": (datetime.now(UTC) + timedelta(days=2)).isoformat(),
            "status": "scheduled",
        },
    )
    assert invalid_interview.status_code in {400, 404}
