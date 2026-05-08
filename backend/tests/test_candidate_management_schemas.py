from datetime import datetime, timezone
from uuid import uuid4

from app.candidate_management.schemas import (
    BulkUploadRequest,
    CandidateBulkStageUpdateRequest,
    CandidateCreate,
    InteractionResponse,
)


def test_candidate_create_rejects_invalid_phone_chars() -> None:
    try:
        CandidateCreate(
            first_name="A",
            last_name="B",
            email="a@example.com",
            phone="12345#bad",
        )
        assert False, "Expected validation error for invalid phone"
    except Exception as exc:  # noqa: BLE001
        assert "phone contains invalid characters" in str(exc)


def test_bulk_stage_update_accepts_string_candidate_ids() -> None:
    cid = str(uuid4())
    model = CandidateBulkStageUpdateRequest(candidate_ids=[cid, cid], stage="interview")
    assert model.candidate_ids == [cid, cid]
    assert model.stage.value == "interview"


def test_bulk_upload_request_requires_non_empty_files() -> None:
    try:
        BulkUploadRequest(files=["   "])
        assert False, "Expected validation error for empty file keys"
    except Exception as exc:  # noqa: BLE001
        assert "at least one non-empty file key is required" in str(exc)


def test_interaction_response_coerces_non_object_metadata() -> None:
    cid = uuid4()
    oid = uuid4()
    wid = uuid4()
    model = InteractionResponse.model_validate(
        {
            "id": uuid4(),
            "candidate_id": cid,
            "org_id": oid,
            "workspace_id": wid,
            "interaction_type": "note",
            "title": None,
            "body": None,
            "metadata": ["not", "a", "dict"],
            "actor_user_id": None,
            "actor_role": None,
            "created_at": datetime.now(timezone.utc),
        }
    )
    assert model.metadata is not None
    assert model.metadata.get("_legacy_wrapped") is True
    assert model.metadata.get("value") == ["not", "a", "dict"]


def test_interaction_response_accepts_interaction_metadata_alias() -> None:
    cid = uuid4()
    oid = uuid4()
    wid = uuid4()
    model = InteractionResponse.model_validate(
        {
            "id": uuid4(),
            "candidate_id": cid,
            "org_id": oid,
            "workspace_id": wid,
            "interaction_type": "system",
            "title": None,
            "body": None,
            "interaction_metadata": "legacy-string",
            "actor_user_id": None,
            "actor_role": None,
            "created_at": datetime.now(timezone.utc),
        }
    )
    assert model.metadata is not None
    assert model.metadata.get("_legacy_wrapped") is True
    assert model.metadata.get("value") == "legacy-string"

