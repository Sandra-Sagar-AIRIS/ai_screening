from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from jose import jwt

import app.main as main_module
from app.core.config import get_settings
from app.db.session import get_db
from app.services.pipeline_service import PipelineService

pytestmark = pytest.mark.unit


class _ProfileDbStub:
    def __init__(self, profile: object | None) -> None:
        self._profile = profile

    def scalar(self, *_args, **_kwargs):
        return self._profile


def _db_override_with_profile(profile: object | None):
    def _override():
        yield _ProfileDbStub(profile)

    return _override


def test_401_when_missing_auth_context(client):
    response = client.get("/api/v1/candidates")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing authenticated user context."


def test_401_when_bearer_token_is_invalid(client):
    response = client.get(
        "/api/v1/candidates",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication token."


def test_403_when_token_org_does_not_match_requested_org(client):
    settings = get_settings()
    user_id = str(uuid4())
    profile_org = str(uuid4())
    mismatch_org = str(uuid4())

    token = jwt.encode({"sub": user_id}, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    profile = SimpleNamespace(id=user_id, organization_id=profile_org, role="recruiter")
    main_module.app.dependency_overrides[get_db] = _db_override_with_profile(profile)

    response = client.get(
        "/api/v1/candidates",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Organization-Id": mismatch_org,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden: organization scope mismatch."


def test_404_when_pipeline_not_found(client, force_auth, monkeypatch):
    def _raise_not_found(self, pipeline_id, organization_id):
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Pipeline not found.")

    monkeypatch.setattr(PipelineService, "get_pipeline_by_id", _raise_not_found)

    response = client.get(f"/api/v1/pipelines/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Pipeline not found."


def test_409_when_creating_duplicate_pipeline(client, force_auth, monkeypatch):
    def _raise_conflict(self, organization_id, payload):
        from fastapi import HTTPException

        raise HTTPException(status_code=409, detail="A pipeline already exists for this candidate and job.")

    monkeypatch.setattr(PipelineService, "create_pipeline", _raise_conflict)
    response = client.post(
        "/api/v1/pipelines",
        json={
            "candidate_id": str(uuid4()),
            "job_id": str(uuid4()),
            "stage": "applied",
            "status": "active",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "A pipeline already exists for this candidate and job."


def test_patch_pipeline_stage_returns_updated_record(client, force_auth, monkeypatch):
    pipeline_id = uuid4()
    organization_id = uuid4()
    candidate_id = uuid4()
    job_id = uuid4()
    now = datetime.now(timezone.utc)

    pipeline = SimpleNamespace(
        id=pipeline_id,
        organization_id=organization_id,
        candidate_id=candidate_id,
        job_id=job_id,
        stage="screening",
        status="active",
        notes=None,
        created_at=now,
        updated_at=now,
    )

    def _update_pipeline(self, pipeline_id, organization_id, current_user, payload):
        return pipeline

    monkeypatch.setattr(PipelineService, "update_pipeline", _update_pipeline)

    response = client.patch(
        f"/api/v1/pipeline/{pipeline_id}",
        json={"stage": "Screening"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(pipeline_id)
    assert body["stage"] == "screening"


def test_422_when_payload_is_invalid(client, auth_headers):
    response = client.post(
        "/api/v1/candidates",
        headers=auth_headers,
        json={
            "first_name": "",
            "last_name": "User",
            "email": "not-an-email",
        },
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert len(detail) >= 1


def test_403_when_viewer_attempts_to_create_candidate(client, auth_headers):
    viewer_headers = {**auth_headers, "X-User-Role": "client_viewer"}
    response = client.post(
        "/api/v1/candidates",
        headers=viewer_headers,
        json={
            "first_name": "Read",
            "last_name": "Only",
            "email": "readonly@example.com",
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden: insufficient permissions."


def test_401_when_role_header_is_invalid(client, auth_headers):
    invalid_headers = {**auth_headers, "X-User-Role": "super_admin"}
    response = client.get("/api/v1/candidates", headers=invalid_headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid user role in auth context."
