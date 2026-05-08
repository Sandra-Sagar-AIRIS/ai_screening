from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.job import Job
from app.models.job_status_history import JobStatusHistory
from app.models.job_skill import JobSkill
from app.models.pipeline import Pipeline

pytestmark = pytest.mark.integration


def _create_candidate_payload(seed: str) -> dict[str, str]:
    return {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": f"jane-{seed}@example.com",
    }


def _create_client_payload(seed: str) -> dict[str, str]:
    return {"name": f"Acme {seed}", "email": f"client-{seed}@example.com"}


def _create_job_payload(*, client_id: UUID, title: str, status: str, **kwargs) -> dict[str, object]:
    payload: dict[str, object] = {
        "client_id": str(client_id),
        "title": title,
        "status": status,
    }
    payload.update(kwargs)
    return payload


def test_create_job_rejects_invalid_salary_range(client, auth_headers):
    seed = uuid4().hex[:8]
    client_res = client.post(
        "/api/v1/clients",
        headers=auth_headers,
        json=_create_client_payload(seed),
    )
    assert client_res.status_code == 201
    client_id = client_res.json()["id"]

    res = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(
            client_id=UUID(client_id),
            title=f"Backend Engineer {seed}",
            status="open",
            salary_min=200000,
            salary_max=100000,
        ),
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "INVALID_SALARY_RANGE"


def test_create_job_rejects_invalid_experience_range(client, auth_headers):
    seed = uuid4().hex[:8]
    client_res = client.post("/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed))
    assert client_res.status_code == 201
    client_id = client_res.json()["id"]

    res = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(
            client_id=UUID(client_id),
            title=f"Backend Engineer {seed}",
            status="open",
            experience_min_years=8,
            experience_max_years=3,
        ),
    )
    assert res.status_code == 400
    assert res.json()["detail"]["error"] == "INVALID_EXPERIENCE_RANGE"


def test_status_transition_draft_to_filled_returns_400(client, auth_headers):
    seed = uuid4().hex[:8]
    client_res = client.post("/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed))
    client_id = client_res.json()["id"]

    job_res = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(
            client_id=UUID(client_id),
            title=f"Engineer {seed}",
            status="draft",
        ),
    )
    job_id = job_res.json()["id"]

    res = client.patch(f"/api/v1/jobs/{job_id}/status", headers=auth_headers, json={"status": "filled"})
    assert res.status_code == 400
    assert "Invalid status transition" in res.json()["detail"]


def test_status_transition_draft_to_open_succeeds(client, auth_headers, db_session: Session):
    seed = uuid4().hex[:8]
    client_res = client.post("/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed))
    client_id = client_res.json()["id"]

    job_res = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(
            client_id=UUID(client_id),
            title=f"Engineer {seed}",
            status="draft",
        ),
    )
    job_id = job_res.json()["id"]

    res = client.patch(f"/api/v1/jobs/{job_id}/status", headers=auth_headers, json={"status": "open"})
    assert res.status_code == 200
    assert res.json()["status"] == "open"

    job = db_session.scalar(select(Job).where(Job.id == UUID(job_id)))
    assert job is not None
    assert job.status == "open"
    history = db_session.scalars(select(JobStatusHistory).where(JobStatusHistory.job_id == UUID(job_id))).all()
    assert len(history) == 1
    assert history[0].previous_status == "draft"
    assert history[0].new_status == "open"


def test_submit_candidate_to_open_job_creates_submission_and_pipeline(
    client, auth_headers, db_session: Session
):
    seed = uuid4().hex[:8]
    candidate_id = client.post("/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(seed)).json()[
        "id"
    ]
    client_id = client.post("/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=f"Engineer {seed}", status="open"),
    ).json()["id"]

    res = client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": "Excellent hire potential"},
    )
    assert res.status_code == 201
    assert res.json()["submission_status"] == "pending"

    pipeline = db_session.scalar(
        select(Pipeline).where(
            Pipeline.candidate_id == UUID(candidate_id),
            Pipeline.job_id == UUID(job_id),
        )
    )
    assert pipeline is not None
    assert pipeline.stage == "applied"


def test_submit_duplicate_candidate_to_job_returns_400(client, auth_headers):
    seed = uuid4().hex[:8]
    candidate_id = client.post("/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(seed)).json()[
        "id"
    ]
    client_id = client.post("/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=f"Engineer {seed}", status="open"),
    ).json()["id"]

    res1 = client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )
    assert res1.status_code == 201

    res2 = client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )
    assert res2.status_code == 400
    assert res2.json()["detail"]["error"] == "DUPLICATE_SUBMISSION"


def test_submit_candidate_to_draft_job_returns_409(client, auth_headers):
    seed = uuid4().hex[:8]
    candidate_id = client.post("/api/v1/candidates", headers=auth_headers, json=_create_candidate_payload(seed)).json()[
        "id"
    ]
    client_id = client.post("/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(client_id=UUID(client_id), title=f"Engineer {seed}", status="draft"),
    ).json()["id"]

    res = client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )
    assert res.status_code == 409
    assert res.json()["detail"] == "JOB_NOT_OPEN"


def test_job_search_skills_filters_with_and_logic(client, auth_headers, db_session: Session):
    seed = uuid4().hex[:8]
    client_id = client.post("/api/v1/clients", headers=auth_headers, json=_create_client_payload(seed)).json()["id"]

    # Job 1: requires both Python and FastAPI
    job1_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(
            client_id=UUID(client_id),
            title=f"Job A {seed}",
            status="open",
            required_skills=["Python", "FastAPI"],
        ),
    ).json()["id"]

    # Job 2: requires only Python
    job2_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json=_create_job_payload(
            client_id=UUID(client_id),
            title=f"Job B {seed}",
            status="open",
            required_skills=["Python"],
        ),
    ).json()["id"]

    res = client.get(
        "/api/v1/jobs/search",
        headers=auth_headers,
        params={"status": "open", "skills": "Python,FastAPI", "limit": 50, "offset": 0},
    )
    assert res.status_code == 200
    returned = res.json()
    returned_ids = {j["id"] for j in returned}
    assert UUID(job1_id) in {UUID(x) for x in returned_ids}
    assert UUID(job2_id) not in {UUID(x) for x in returned_ids}

    # Sanity check that job skills were stored.
    skills = db_session.scalars(select(JobSkill.skill).where(JobSkill.job_id == UUID(job1_id))).all()
    assert any(s.lower() == "python" for s in skills)
    assert any(s.lower() == "fastapi" for s in skills)

