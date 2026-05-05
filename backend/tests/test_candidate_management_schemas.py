from uuid import uuid4

from app.candidate_management.schemas import BulkUploadRequest, CandidateBulkStageUpdateRequest, CandidateCreate


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

