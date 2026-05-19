"""Fast candidate text search helpers (DB ILIKE + optional pg_trgm index)."""

from __future__ import annotations

from sqlalchemy import or_

from app.candidate_management.models import Candidate


def normalize_search_query(query: str | None) -> str | None:
    if query is None:
        return None
    cleaned = " ".join(str(query).strip().split())
    return cleaned if cleaned else None


def escape_ilike_pattern(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_candidate_text_search_filter(query: str | None):
    """Return a SQLAlchemy filter for case-insensitive substring search, or None."""
    normalized = normalize_search_query(query)
    if not normalized:
        return None

    pattern = f"%{escape_ilike_pattern(normalized)}%"
    clauses = [
        Candidate.full_name.ilike(pattern, escape="\\"),
        Candidate.first_name.ilike(pattern, escape="\\"),
        Candidate.last_name.ilike(pattern, escape="\\"),
        Candidate.email.ilike(pattern, escape="\\"),
        Candidate.phone.ilike(pattern, escape="\\"),
        Candidate.location.ilike(pattern, escape="\\"),
        Candidate.headline.ilike(pattern, escape="\\"),
    ]
    return or_(*clauses)
