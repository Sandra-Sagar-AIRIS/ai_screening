"""AIR-510–513: Candidate soft delete, list exclusion, restore, pipeline withdraw, audit."""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.candidate_management.models import CandidateAuditLog
from app.models.candidate import Candidate as LegacyCandidate
from app.models.pipeline import Pipeline

pytestmark = pytest.mark.integration


def _workspace_headers(auth_headers: dict[str, str]) -> dict[str, str]:
    org_id = auth_headers["X-Organization-Id"]
    return {**auth_headers, "X-Workspace-Id": org_id}


def _create_cm_candidate(client, auth_headers: dict[str, str]) -> str:
    seed = uuid4().hex[:8]
    res = client.post(
        "/api/v1/candidate-management/candidates",
        headers=_workspace_headers(auth_headers),
        json={
            "first_name": "Soft",
            "last_name": f"Delete{seed}",
            "email": f"soft.del.{seed}@example.com",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["data"]["id"]


@pytest.mark.integration
def test_delete_soft_deletes_and_excludes_from_list(client, auth_headers, db_session):
    candidate_id = _create_cm_candidate(client, auth_headers)
    headers = _workspace_headers(auth_headers)

    archive = client.post(
        f"/api/v1/candidate-management/candidates/{candidate_id}/archive",
        headers=headers,
    )
    assert archive.status_code == 200, archive.text
    assert archive.json()["data"].get("archived") is True

    row = db_session.scalar(select(LegacyCandidate).where(LegacyCandidate.id == UUID(candidate_id)))
    assert row is not None
    assert row.is_deleted is True
    assert row.deleted_at is not None

    listing = client.get(
        "/api/v1/candidate-management/candidates",
        headers=headers,
    )
    assert listing.status_code == 200
    ids = [item["id"] for item in listing.json()["data"]]
    assert candidate_id not in ids

    audit_rows = list(
        db_session.scalars(
            select(CandidateAuditLog).where(
                CandidateAuditLog.candidate_id == UUID(candidate_id),
                CandidateAuditLog.action == "candidate_archived",
            )
        )
    )
    assert len(audit_rows) >= 1


@pytest.mark.integration
def test_delete_endpoint_hard_deletes(client, auth_headers, db_session):
    seed = uuid4().hex[:8]
    headers = _workspace_headers(auth_headers)
    candidate_id = _create_cm_candidate(client, auth_headers)

    delete = client.delete(
        f"/api/v1/candidate-management/candidates/{candidate_id}",
        headers=headers,
    )
    assert delete.status_code == 200, delete.text
    assert delete.json()["data"].get("hard_deleted") is True

    row = db_session.scalar(select(LegacyCandidate).where(LegacyCandidate.id == UUID(candidate_id)))
    assert row is None


@pytest.mark.integration
def test_legacy_archive_endpoint_soft_deletes(client, auth_headers, db_session):
    seed = uuid4().hex[:8]
    create = client.post(
        "/api/v1/candidates",
        headers=auth_headers,
        json={
            "first_name": "Legacy",
            "last_name": f"Soft{seed}",
            "email": f"legacy.soft.{seed}@example.com",
        },
    )
    assert create.status_code == 201
    candidate_id = create.json()["id"]

    archive = client.post(f"/api/v1/candidates/{candidate_id}/archive", headers=auth_headers)
    assert archive.status_code == 200
    assert archive.json().get("archived") is True

    row = db_session.get(LegacyCandidate, UUID(candidate_id))
    assert row is not None
    assert row.is_deleted is True


@pytest.mark.integration
def test_admin_restore_clears_soft_delete(client, auth_headers, db_session):
    candidate_id = _create_cm_candidate(client, auth_headers)
    headers = _workspace_headers(auth_headers)

    client.post(f"/api/v1/candidate-management/candidates/{candidate_id}/archive", headers=headers)

    admin_headers = {**headers, "X-User-Role": "admin"}
    restore = client.patch(
        f"/api/v1/candidate-management/candidates/{candidate_id}/restore",
        headers=admin_headers,
    )
    assert restore.status_code == 200, restore.text

    row = db_session.scalar(select(LegacyCandidate).where(LegacyCandidate.id == UUID(candidate_id)))
    assert row is not None
    assert row.is_deleted is False
    assert row.deleted_at is None

    audit_rows = list(
        db_session.scalars(
            select(CandidateAuditLog).where(
                CandidateAuditLog.candidate_id == UUID(candidate_id),
                CandidateAuditLog.action == "candidate_restored",
            )
        )
    )
    assert len(audit_rows) >= 1


@pytest.mark.integration
def test_restore_requires_admin(client, auth_headers):
    candidate_id = _create_cm_candidate(client, auth_headers)
    headers = _workspace_headers(auth_headers)
    client.post(f"/api/v1/candidate-management/candidates/{candidate_id}/archive", headers=headers)

    denied = client.patch(
        f"/api/v1/candidate-management/candidates/{candidate_id}/restore",
        headers=headers,
    )
    assert denied.status_code == 403


@pytest.mark.integration
def test_soft_delete_withdraws_active_pipeline(
    client, auth_headers, db_session,
):
    seed = uuid4().hex[:8]
    headers = _workspace_headers(auth_headers)
    candidate_id = _create_cm_candidate(client, auth_headers)

    client_id = client.post(
        "/api/v1/clients", headers=auth_headers, json={"name": f"C {seed}", "legal_name": f"C {seed}", "industry": "Tech"}
    ).json()["id"]
    job_id = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json={
            "client_id": client_id,
            "title": f"Job {seed}",
            "description": "d",
            "status": "open",
        },
    ).json()["id"]

    submit = client.post(
        f"/api/v1/jobs/{job_id}/submit",
        headers=auth_headers,
        json={"candidate_id": candidate_id, "notes": None},
    )
    assert submit.status_code == 201

    pipeline = db_session.scalar(
        select(Pipeline).where(
            Pipeline.candidate_id == UUID(candidate_id),
            Pipeline.job_id == UUID(job_id),
        )
    )
    assert pipeline is not None
    assert pipeline.status == "active"

    client.post(f"/api/v1/candidate-management/candidates/{candidate_id}/archive", headers=headers)

    db_session.refresh(pipeline)
    assert pipeline.status == "withdrawn"
