"""AI-003: Pydantic schemas for interview question generation."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


# ── Request ───────────────────────────────────────────────────────────────────

class GenerateInterviewQuestionsRequest(BaseModel):
    """Generate 8-12 role-specific interview questions.

    Supply either (job_title + job_description + required_skills) directly,
    or a job_id to let the server look up job details.
    """
    job_title: str = Field(..., min_length=1, max_length=255)
    job_description: str = Field(..., min_length=1, max_length=8000)
    required_skills: list[str] = Field(default_factory=list)


# ── Response ──────────────────────────────────────────────────────────────────

class InterviewQuestionSchema(BaseModel):
    category: str  # "technical" | "behavioural" | "situational"
    question_text: str
    follow_up_probe: str | None = None
    ideal_answer_traits: list[str]


class GenerateInterviewQuestionsResponse(BaseModel):
    questions: list[InterviewQuestionSchema]
    questions_by_category: dict[str, int]
    provider_used: str
    fallback_used: bool
    duration_ms: int
