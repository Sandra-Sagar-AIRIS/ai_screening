from __future__ import annotations

from uuid import uuid4

import pytest

from app.candidate_management.communication_schemas import CommunicationSendRequest, CommunicationWhatsAppSendRequest
from app.candidate_management.communication_service import PLACEHOLDER_RE, CommunicationService


pytestmark = pytest.mark.unit


def test_send_request_rejects_mixed_raw_and_template_modes() -> None:
    with pytest.raises(Exception):
        CommunicationSendRequest(
            provider="gmail",
            to_email="candidate@example.com",
            subject="Hello",
            body="Body",
            template_id=uuid4(),
        )


def test_send_request_requires_subject_for_raw_mode() -> None:
    with pytest.raises(Exception):
        CommunicationSendRequest(
            provider="gmail",
            to_email="candidate@example.com",
            body="Body only",
        )


def test_placeholder_regex_extracts_expected_fields() -> None:
    text = "Hi {{candidate_name}}, interview is at {{interview_time}} in {{interview_mode}}."
    found = PLACEHOLDER_RE.findall(text)
    assert found == ["candidate_name", "interview_time", "interview_mode"]


def test_send_request_allows_subjectless_draft_mode() -> None:
    payload = CommunicationSendRequest(
        provider="gmail",
        to_email="candidate@example.com",
        body="Draft body",
        save_as_draft=True,
    )
    assert payload.save_as_draft is True


def test_whatsapp_send_requires_body_or_template() -> None:
    with pytest.raises(Exception):
        CommunicationWhatsAppSendRequest(to_phone="+919999999999")


def test_whatsapp_phone_normalization_accepts_indian_formats() -> None:
    service = CommunicationService(db=None)  # type: ignore[arg-type]
    assert service._normalize_whatsapp_phone("9347886094") == "whatsapp:+919347886094"
    assert service._normalize_whatsapp_phone("919347886094") == "whatsapp:+919347886094"
    assert service._normalize_whatsapp_phone("+919347886094") == "whatsapp:+919347886094"


def test_whatsapp_phone_normalization_rejects_invalid_number() -> None:
    service = CommunicationService(db=None)  # type: ignore[arg-type]
    with pytest.raises(Exception):
        service._normalize_whatsapp_phone("12345")
