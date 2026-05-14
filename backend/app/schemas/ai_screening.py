"""Pydantic schemas for the AI Screening layer."""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class ScreeningStatus(StrEnum):
    PENDING = "pending"
    GENERATING_QUESTIONS = "generating_questions"
    QUESTIONS_READY = "questions_ready"
    EVALUATING = "evaluating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScreeningType(StrEnum):
    TECHNICAL = "technical"
    HR = "hr"
    COMMUNICATION = "communication"
    LEADERSHIP = "leadership"
    BEHAVIORAL = "behavioral"
    ROLE_FIT = "role_fit"


class ScreeningRecommendation(StrEnum):
    STRONG_PROCEED = "strong_proceed"
    PROCEED = "proceed"
    NEEDS_MANUAL_REVIEW = "needs_manual_review"
    WEAK_MATCH = "weak_match"
    REJECT_RECOMMENDATION = "reject_recommendation"


class QuestionCategory(StrEnum):
    TECHNICAL_DEPTH = "technical_depth"
    ARCHITECTURE = "architecture"
    COMMUNICATION = "communication"
    BEHAVIORAL = "behavioral"
    PROBLEM_SOLVING = "problem_solving"
    SCALABILITY = "scalability"
    DEBUGGING = "debugging"
    LEADERSHIP = "leadership"


class QuestionDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AnswerSourceType(StrEnum):
    MANUAL = "manual"
    UPLOADED = "uploaded"
    LINK_RESPONSE = "link_response"


class RecruiterDecision(StrEnum):
    ADVANCE = "advance"
    REJECT = "reject"
    HOLD = "hold"
    NEEDS_REVIEW = "needs_review"


# ── Create / Update payloads ─────────────────────────────────────────────────

class AIScreeningCreate(BaseModel):
    candidate_id: UUID
    job_id: UUID | None = None
    screening_type: ScreeningType = ScreeningType.TECHNICAL


class AIScreeningUpdate(BaseModel):
    screening_type: ScreeningType | None = None
    status: ScreeningStatus | None = None
    recruiter_summary: str | None = None


class AIScreeningRecruiterDecision(BaseModel):
    decision: RecruiterDecision
    notes: str | None = Field(default=None, max_length=2000)


class AnswerUpsert(BaseModel):
    answer_text: str = Field(min_length=1, max_length=10_000)
    source_type: AnswerSourceType = AnswerSourceType.MANUAL


class StartScreeningPayload(BaseModel):
    """Payload for the /ai-screenings/start convenience endpoint.

    Creates a screening + optionally moves the candidate's pipeline to ai_screening stage.
    """
    candidate_id: UUID
    job_id: UUID | None = None
    screening_type: ScreeningType = ScreeningType.TECHNICAL
    # When True the candidate's pipeline entry for this job is moved to ai_screening stage.
    move_pipeline_stage: bool = True
    # pipeline_id to move; required only when move_pipeline_stage=True and job_id is set
    pipeline_id: UUID | None = None


class MoveStagePayload(BaseModel):
    """Move the pipeline entry of a screening's candidate to the given stage."""
    pipeline_id: UUID
    stage: str  # validated against known stages at runtime


# ── Response schemas ──────────────────────────────────────────────────────────

class AIScreeningQuestionResponse(BaseModel):
    id: UUID
    screening_id: UUID
    category: str
    difficulty: str
    position: int
    question_text: str
    expected_signals: dict | None
    generated_by_ai: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIScreeningAnswerResponse(BaseModel):
    id: UUID
    screening_id: UUID
    question_id: UUID
    answer_text: str
    recruiter_entered: bool
    source_type: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIScreeningEvaluationResponse(BaseModel):
    id: UUID
    screening_id: UUID
    question_id: UUID
    ai_score: int | None
    communication_rating: int | None
    technical_rating: int | None
    strengths: list | None
    concerns: list | None
    reasoning: str | None
    follow_up_suggestion: str | None
    confidence: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AIScreeningResponse(BaseModel):
    id: UUID
    organization_id: UUID
    candidate_id: UUID
    job_id: UUID | None
    created_by: UUID | None
    status: str
    screening_type: str
    ai_model: str | None
    overall_score: float | None
    communication_score: float | None
    technical_score: float | None
    confidence_score: float | None
    recommendation: str | None
    ai_summary: str | None
    recruiter_summary: str | None
    recruiter_decision: str | None
    recruiter_notes: str | None
    prompt_tokens_used: int | None
    completion_tokens_used: int | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AIScreeningDetailResponse(AIScreeningResponse):
    """Full screening response including questions, answers, and evaluations."""

    questions: list[AIScreeningQuestionResponse] = []
    answers: list[AIScreeningAnswerResponse] = []
    evaluations: list[AIScreeningEvaluationResponse] = []

    # Enriched candidate/job metadata for the review panel
    candidate_name: str | None = None
    candidate_email: str | None = None
    job_title: str | None = None
    ats_score: float | None = None
    ats_recommendation: str | None = None


class AIScreeningListItem(BaseModel):
    """Lightweight list-view row."""

    id: UUID
    candidate_id: UUID
    job_id: UUID | None
    status: str
    screening_type: str
    overall_score: float | None
    recommendation: str | None
    recruiter_decision: str | None
    created_at: datetime
    completed_at: datetime | None

    # Denormalized for the list table
    candidate_name: str | None = None
    candidate_email: str | None = None
    job_title: str | None = None

    model_config = ConfigDict(from_attributes=True)
