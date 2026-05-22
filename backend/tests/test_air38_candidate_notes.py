"""AIR-38: Candidate notes API and soft-hide behavior."""
from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.candidate_management.schemas import NoteCreate


def test_note_create_rejects_whitespace_only_content():
    with pytest.raises(ValidationError):
        NoteCreate(content="   ")


def _workspace_headers(auth_headers: dict[str, str]) -> dict[str, str]:
    org_id = auth_headers["X-Organization-Id"]
    return {**auth_headers, "X-Workspace-Id": org_id}


def _create_cm_candidate(client, auth_headers: dict[str, str]) -> str:
    seed = uuid4().hex[:8]
    res = client.post(
        "/api/v1/candidate-management/candidates",
        headers=_workspace_headers(auth_headers),
        json={
            "first_name": "Note",
            "last_name": f"Test{seed}",
            "email": f"note.test.{seed}@example.com",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    return body["data"]["id"]


@pytest.mark.integration
def test_post_and_list_candidate_notes(client, auth_headers):
    candidate_id = _create_cm_candidate(client, auth_headers)
    headers = _workspace_headers(auth_headers)

    create = client.post(
        f"/api/v1/candidates/{candidate_id}/notes",
        headers=headers,
        json={"content": "Follow up next week"},
    )
    assert create.status_code == 201, create.text
    note = create.json()
    assert note["content"] == "Follow up next week"
    assert note["author_user_id"] == auth_headers["X-User-Id"]
    assert note["created_at"]
    assert note["hidden"] is False

    listing = client.get(f"/api/v1/candidates/{candidate_id}/notes", headers=headers)
    assert listing.status_code == 200
    data = listing.json()
    assert data["total"] >= 1
    assert any(row["id"] == note["id"] for row in data["data"])


@pytest.mark.integration
def test_admin_soft_hide_hides_note_from_recruiters(client, auth_headers):
    candidate_id = _create_cm_candidate(client, auth_headers)
    headers = _workspace_headers(auth_headers)

    create = client.post(
        f"/api/v1/candidates/{candidate_id}/notes",
        headers=headers,
        json={"content": "Sensitive internal note"},
    )
    assert create.status_code == 201
    note_id = create.json()["id"]

    admin_headers = {**headers, "X-User-Role": "admin"}
    hide = client.post(
        f"/api/v1/candidates/{candidate_id}/notes/{note_id}/hide",
        headers=admin_headers,
    )
    assert hide.status_code == 200, hide.text
    assert hide.json()["hidden"] is True

    recruiter_list = client.get(
        f"/api/v1/candidates/{candidate_id}/notes",
        headers=headers,
    )
    assert recruiter_list.status_code == 200
    visible_ids = [row["id"] for row in recruiter_list.json()["data"]]
    assert note_id not in visible_ids

    admin_list = client.get(
        f"/api/v1/candidates/{candidate_id}/notes",
        headers=admin_headers,
    )
    assert admin_list.status_code == 200
    admin_ids = [row["id"] for row in admin_list.json()["data"]]
    assert note_id in admin_ids


@pytest.mark.integration
def test_post_note_rejects_blank_content(client, auth_headers):
    candidate_id = _create_cm_candidate(client, auth_headers)
    headers = _workspace_headers(auth_headers)

    rejected = client.post(
        f"/api/v1/candidates/{candidate_id}/notes",
        headers=headers,
        json={"content": "   "},
    )
    assert rejected.status_code == 422


@pytest.mark.integration
def test_hide_requires_admin(client, auth_headers):
    candidate_id = _create_cm_candidate(client, auth_headers)
    headers = _workspace_headers(auth_headers)

    create = client.post(
        f"/api/v1/candidates/{candidate_id}/notes",
        headers=headers,
        json={"content": "Cannot hide as recruiter"},
    )
    note_id = create.json()["id"]

    denied = client.post(
        f"/api/v1/candidates/{candidate_id}/notes/{note_id}/hide",
        headers=headers,
    )
    assert denied.status_code == 403
