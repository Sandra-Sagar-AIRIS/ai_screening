from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class CopilotSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    SUMMARIZED = "summarized"


class SuggestionType(StrEnum):
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"
    SKILL_GAP = "skill_gap"
    DEEP_DIVE = "deep_dive"
    CLOSING = "closing"


class TranscriptSpeaker(StrEnum):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"
    UNKNOWN = "unknown"


# ── Transcript ────────────────────────────────────────────────────────────────

class TranscriptSegmentCreate(BaseModel):
    speaker: TranscriptSpeaker = TranscriptSpeaker.UNKNOWN
    content: str = Field(..., min_length=1, max_length=8000)
    offset_ms: int | None = None
    duration_ms: int | None = None
    source: str = "manual"


class TranscriptSegmentResponse(BaseModel):
    id: UUID
    session_id: UUID
    interview_id: UUID
    speaker: str
    content: str
    offset_ms: int | None
    duration_ms: int | None
    source: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Suggestions ───────────────────────────────────────────────────────────────

class SuggestRequest(BaseModel):
    """Optional hints the frontend can pass when requesting new suggestions."""
    context_hint: str | None = Field(
        default=None,
        max_length=500,
        description="E.g. 'candidate mentioned Redis — dig deeper'",
    )
    suggestion_types: list[SuggestionType] | None = None
    count: int = Field(default=3, ge=1, le=8)


class AISuggestionResponse(BaseModel):
    id: UUID
    session_id: UUID
    interview_id: UUID
    suggestion_type: str
    question_text: str
    rationale: str | None
    target_skills: list[str] | None
    difficulty: str | None
    used: bool
    used_at: datetime | None
    dismissed: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SuggestionUseRequest(BaseModel):
    """Marks a suggestion as used (or dismissed)."""
    used: bool = True
    dismissed: bool = False


# ── Session ───────────────────────────────────────────────────────────────────

class CopilotSessionResponse(BaseModel):
    id: UUID
    organization_id: UUID
    interview_id: UUID
    status: str
    summary: dict | None
    skills_covered: dict | None
    prompt_tokens_used: int
    completion_tokens_used: int
    created_at: datetime
    updated_at: datetime
    summarized_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# ── Summary request ───────────────────────────────────────────────────────────

class SummarizeRequest(BaseModel):
    """Trigger post-interview summary generation."""
    force: bool = False  # Re-generate even if summary already exists


# ── WebSocket event envelopes ─────────────────────────────────────────────────

class WsEventType(StrEnum):
    TRANSCRIPT_ADDED = "transcript_added"
    SUGGESTION_READY = "suggestion_ready"
    SUMMARY_READY = "summary_ready"
    SESSION_UPDATED = "session_updated"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"
