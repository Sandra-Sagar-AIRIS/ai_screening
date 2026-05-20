"""CAND-006: Pydantic schemas for candidate duplicate detection and merge."""
from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


# ── Request models ────────────────────────────────────────────────────────────

class DuplicateCheckRequest(BaseModel):
    email: str | None = Field(default=None, description="Email address to check for duplicates.")
    phone: str | None = Field(default=None, description="Phone number to check for duplicates.")
    exclude_id: UUID | None = Field(
        default=None,
        description="Candidate ID to exclude from the check (useful when editing an existing record).",
    )


class MergeRequest(BaseModel):
    duplicate_id: UUID = Field(description="ID of the candidate to be merged (will be soft-deleted).")


# ── Response models ───────────────────────────────────────────────────────────

class DuplicateMatchOut(BaseModel):
    """A candidate that may be a duplicate."""

    candidate_id: str
    first_name: str
    last_name: str
    email: str
    phone: str | None
    location: str | None
    pipeline_count: int
    confidence: float = Field(ge=0.0, le=1.0)
    match_type: str  # "email" | "phone"


class DuplicateCheckResult(BaseModel):
    """Response body for POST /candidates/check-duplicate."""

    has_duplicates: bool
    matches: list[DuplicateMatchOut]


class MergeResponse(BaseModel):
    """Response body for POST /candidates/{id}/merge."""

    survivor_id: str
    duplicate_id: str
    message: str
