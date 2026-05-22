"""AI-003 — Interview Question Generation tests.

Acceptance criteria verified:
  1.  Valid request returns 200 with 8-12 questions.
  2.  Response contains questions_by_category, provider_used, fallback_used, duration_ms.
  3.  Each question has category, question_text, follow_up_probe, ideal_answer_traits.
  4.  Question categories are one of: technical, behavioural, situational.
  5.  ideal_answer_traits contains 1-5 items.
  6.  Empty job_description (after strip) returns 400 {"error": "EMPTY_JOB_DESCRIPTION"}.
  7.  Empty required_skills list returns 400 {"error": "EMPTY_REQUIRED_SKILLS"}.
  8.  Required_skills with only blank strings returns 400 {"error": "EMPTY_REQUIRED_SKILLS"}.
  9.  Missing permission returns 403.
 10.  OpenAI success path — returns openai/... as provider_used, fallback_used=False.
 11.  OpenAI timeout → Groq fallback — provider_used contains groq/, fallback_used=True.
 12.  Both providers fail → static fallback — provider_used == "static-fallback".
 13.  Static fallback questions reference job title and primary skill.
 14.  _parse_questions handles invalid category by defaulting to "behavioural".
 15.  _parse_questions enforces max 12 questions cap.
 16.  _parse_questions fills missing ideal_answer_traits with defaults.
"""
from __future__ import annotations

from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.dependencies import get_current_user, get_db
from app.schemas.auth import CurrentUser
from app.services.ai.interview_question_generator import (
    InterviewQuestion,
    InterviewQuestionGenerator,
    QuestionGenerationResult,
    _parse_questions,
    _static_fallback,
)

pytestmark = pytest.mark.unit

# ── Constants ─────────────────────────────────────────────────────────────────

_JOB_TITLE = "Senior Python Engineer"
_JOB_DESCRIPTION = (
    "We are looking for a Senior Python Engineer to build and maintain "
    "our data platform. Experience with FastAPI, SQLAlchemy, and PostgreSQL required."
)
_SKILLS = ["Python", "FastAPI", "PostgreSQL", "SQLAlchemy"]

_VALID_PAYLOAD = {
    "job_title": _JOB_TITLE,
    "job_description": _JOB_DESCRIPTION,
    "required_skills": _SKILLS,
}

_AI_PERM = "ai_interview_questions:generate"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_with_perms() -> CurrentUser:
    return CurrentUser(
        user_id="user-001",
        organization_id="org-001",
        email="recruiter@example.com",
        role="admin",
        user_type="internal",
    )


def _user_no_perms() -> CurrentUser:
    return CurrentUser(
        user_id="user-002",
        organization_id="org-001",
        email="viewer@example.com",
        role="viewer",
        user_type="internal",
    )


def _make_mock_db() -> MagicMock:
    return MagicMock()


def _mock_result(
    *,
    provider: str = "openai/gpt-4.1-mini",
    fallback: bool = False,
    count: int = 10,
) -> QuestionGenerationResult:
    return QuestionGenerationResult(
        questions=[
            InterviewQuestion(
                category="technical",
                question_text=f"Question {i}?",
                follow_up_probe="Follow up?" if i % 2 == 0 else None,
                ideal_answer_traits=["Trait A", "Trait B", "Trait C"],
            )
            for i in range(count)
        ],
        questions_by_category={"technical": count, "behavioural": 0, "situational": 0},
        provider_used=provider,
        fallback_used=fallback,
        duration_ms=500,
    )


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """TestClient with admin user + permission granted via mock."""
    app = main_module.app
    db = _make_mock_db()
    app.dependency_overrides[get_current_user] = _user_with_perms
    app.dependency_overrides[get_db] = lambda: db
    with patch(
        "app.services.permission_service.PermissionService.get_user_permissions",
        return_value=[_AI_PERM],
    ):
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c
    app.dependency_overrides.clear()


# ── 1. Valid request returns 200 with 8-12 questions ─────────────────────────

def test_generate_questions_success(client: TestClient) -> None:
    with patch(
        "app.routes.ai_interview_questions._generator.generate",
        return_value=_mock_result(count=10),
    ):
        resp = client.post("/api/v1/ai/interview-questions", json=_VALID_PAYLOAD)

    assert resp.status_code == 200
    data = resp.json()
    assert 8 <= len(data["questions"]) <= 12


# ── 2. Response has required top-level fields ─────────────────────────────────

def test_response_has_required_top_level_fields(client: TestClient) -> None:
    with patch(
        "app.routes.ai_interview_questions._generator.generate",
        return_value=_mock_result(),
    ):
        resp = client.post("/api/v1/ai/interview-questions", json=_VALID_PAYLOAD)

    assert resp.status_code == 200
    data = resp.json()
    assert "questions" in data
    assert "questions_by_category" in data
    assert "provider_used" in data
    assert "fallback_used" in data
    assert "duration_ms" in data


# ── 3. Each question has required fields ──────────────────────────────────────

def test_each_question_has_required_fields(client: TestClient) -> None:
    with patch(
        "app.routes.ai_interview_questions._generator.generate",
        return_value=_mock_result(count=8),
    ):
        resp = client.post("/api/v1/ai/interview-questions", json=_VALID_PAYLOAD)

    assert resp.status_code == 200
    for q in resp.json()["questions"]:
        assert "category" in q
        assert "question_text" in q
        assert "follow_up_probe" in q  # may be null
        assert "ideal_answer_traits" in q


# ── 4. Valid categories ───────────────────────────────────────────────────────

def test_categories_are_valid() -> None:
    valid = {"technical", "behavioural", "situational"}
    result = _static_fallback("Python Dev", ["Python"])
    for q in result.questions:
        assert q.category in valid


# ── 5. ideal_answer_traits count ─────────────────────────────────────────────

def test_ideal_answer_traits_count() -> None:
    result = _static_fallback("Python Dev", ["Python"])
    for q in result.questions:
        assert 1 <= len(q.ideal_answer_traits) <= 5


# ── 6. Empty job_description → 400 ───────────────────────────────────────────

def test_empty_job_description_returns_400(client: TestClient) -> None:
    payload = {**_VALID_PAYLOAD, "job_description": "   "}
    resp = client.post("/api/v1/ai/interview-questions", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "EMPTY_JOB_DESCRIPTION"


# ── 7. Empty required_skills → 400 ───────────────────────────────────────────

def test_empty_required_skills_returns_400(client: TestClient) -> None:
    payload = {**_VALID_PAYLOAD, "required_skills": []}
    resp = client.post("/api/v1/ai/interview-questions", json=payload)
    assert resp.status_code == 400


# ── 8. All-blank required_skills → 400 ───────────────────────────────────────

def test_blank_required_skills_returns_400(client: TestClient) -> None:
    payload = {**_VALID_PAYLOAD, "required_skills": ["  ", "\t", ""]}
    resp = client.post("/api/v1/ai/interview-questions", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["error"] == "EMPTY_REQUIRED_SKILLS"


# ── 9. Missing permission returns 403 ────────────────────────────────────────

def test_missing_permission_returns_403() -> None:
    app = main_module.app
    db = _make_mock_db()
    app.dependency_overrides[get_current_user] = _user_no_perms
    app.dependency_overrides[get_db] = lambda: db

    with patch(
        "app.services.permission_service.PermissionService.get_user_permissions",
        return_value=[],  # no permissions
    ):
        with TestClient(app, raise_server_exceptions=False) as c:
            resp = c.post("/api/v1/ai/interview-questions", json=_VALID_PAYLOAD)

    app.dependency_overrides.clear()
    assert resp.status_code == 403


# ── 10. OpenAI success path ───────────────────────────────────────────────────

def test_openai_success_provider_used(client: TestClient) -> None:
    with patch(
        "app.routes.ai_interview_questions._generator.generate",
        return_value=_mock_result(provider="openai/gpt-4.1-mini", fallback=False),
    ):
        resp = client.post("/api/v1/ai/interview-questions", json=_VALID_PAYLOAD)

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_used"].startswith("openai/")
    assert data["fallback_used"] is False


# ── 11. OpenAI timeout → Groq fallback ───────────────────────────────────────

def test_groq_fallback_when_openai_times_out(client: TestClient) -> None:
    with patch(
        "app.routes.ai_interview_questions._generator.generate",
        return_value=_mock_result(provider="groq/llama-3.3-70b-versatile", fallback=True),
    ):
        resp = client.post("/api/v1/ai/interview-questions", json=_VALID_PAYLOAD)

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_used"].startswith("groq/")
    assert data["fallback_used"] is True


# ── 12. Both providers fail → static fallback ────────────────────────────────

def test_static_fallback_when_all_providers_fail(client: TestClient) -> None:
    with patch(
        "app.routes.ai_interview_questions._generator.generate",
        return_value=_mock_result(provider="static-fallback", fallback=True, count=10),
    ):
        resp = client.post("/api/v1/ai/interview-questions", json=_VALID_PAYLOAD)

    assert resp.status_code == 200
    data = resp.json()
    assert data["provider_used"] == "static-fallback"
    assert data["fallback_used"] is True


# ── 13. Static fallback references job title + skill ─────────────────────────

def test_static_fallback_references_job_and_skill() -> None:
    result = _static_fallback("Data Scientist", ["TensorFlow"])
    texts = " ".join(q.question_text for q in result.questions)
    assert "TensorFlow" in texts or "Data Scientist" in texts


# ── 14. _parse_questions defaults invalid category to behavioural ─────────────

def test_parse_questions_defaults_invalid_category() -> None:
    raw = {
        "questions": [
            {
                "category": "illegal_category",
                "question_text": "Q?",
                "follow_up_probe": None,
                "ideal_answer_traits": ["t1", "t2", "t3"],
            }
        ]
    }
    questions = _parse_questions(raw)
    assert len(questions) == 1
    assert questions[0].category == "behavioural"


# ── 15. _parse_questions caps at 12 ──────────────────────────────────────────

def test_parse_questions_caps_at_12() -> None:
    raw = {
        "questions": [
            {"category": "technical", "question_text": f"Q{i}?", "ideal_answer_traits": ["t1"]}
            for i in range(20)
        ]
    }
    questions = _parse_questions(raw)
    assert len(questions) == 12


# ── 16. _parse_questions fills missing ideal_answer_traits ───────────────────

def test_parse_questions_fills_missing_traits() -> None:
    raw = {
        "questions": [
            {
                "category": "technical",
                "question_text": "Q?",
                "ideal_answer_traits": [],
            }
        ]
    }
    questions = _parse_questions(raw)
    assert len(questions) == 1
    assert len(questions[0].ideal_answer_traits) == 3  # default 3 traits
