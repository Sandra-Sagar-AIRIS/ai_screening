"""CAND-006: Duplicate candidate detection service.

Checks for existing candidates that may be duplicates of a prospective new entry,
returning ranked matches with confidence scores. Always org-scoped.

Detection priority:
  1. Email exact match (case-insensitive, normalized) → confidence 1.0
  2. Phone normalized match (last 10 digits)         → confidence 0.9
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.pipeline import Pipeline
from app.services.candidate_dedup.phone_normalizer import normalize_phone

logger = logging.getLogger(__name__)


@dataclass
class DuplicateMatch:
    """A single candidate that is a probable duplicate."""

    candidate_id: str
    first_name: str
    last_name: str
    email: str
    phone: str | None
    location: str | None
    pipeline_count: int
    confidence: float  # 0.0 – 1.0
    match_type: str   # "email" | "phone"


@dataclass
class DuplicateCheckResult:
    """Result of a duplicate check."""

    has_duplicates: bool
    matches: list[DuplicateMatch] = field(default_factory=list)


class DuplicateDetectionService:
    """Check for duplicate candidates within an organisation."""

    def check(
        self,
        *,
        email: str | None,
        phone: str | None,
        org_id: UUID,
        db: Session,
        exclude_id: UUID | None = None,
    ) -> DuplicateCheckResult:
        """Return duplicate matches for the given contact details.

        Parameters
        ----------
        email:
            Email to check (normalised to lower-case internally).
        phone:
            Raw phone string to check (normalised internally).
        org_id:
            Organisation scope — only searches within this org.
        db:
            SQLAlchemy session.
        exclude_id:
            Skip a candidate with this ID (useful when editing an existing record).
        """
        matches: list[DuplicateMatch] = []
        seen_ids: set[UUID] = set()

        norm_email = email.strip().lower() if email and email.strip() else None
        norm_phone = normalize_phone(phone)

        # ── 1. Email exact match ──────────────────────────────────────────────
        if norm_email:
            candidates = self._query_candidates(db, org_id, exclude_id)
            for c in candidates:
                if c.email and c.email.strip().lower() == norm_email:
                    if c.id not in seen_ids:
                        seen_ids.add(c.id)
                        matches.append(self._build_match(c, db, confidence=1.0, match_type="email"))

        # ── 2. Phone normalised match ─────────────────────────────────────────
        if norm_phone:
            candidates = self._query_candidates(db, org_id, exclude_id)
            for c in candidates:
                if c.id in seen_ids:
                    continue
                if normalize_phone(c.phone) == norm_phone:
                    seen_ids.add(c.id)
                    matches.append(self._build_match(c, db, confidence=0.9, match_type="phone"))

        # Sort by confidence descending
        matches.sort(key=lambda m: m.confidence, reverse=True)

        logger.debug(
            "cand006.dedup.check",
            extra={
                "org_id": str(org_id),
                "email_provided": bool(norm_email),
                "phone_provided": bool(norm_phone),
                "matches_found": len(matches),
            },
        )

        return DuplicateCheckResult(has_duplicates=bool(matches), matches=matches)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _query_candidates(
        self, db: Session, org_id: UUID, exclude_id: UUID | None
    ) -> list[Candidate]:
        stmt = (
            select(Candidate)
            .where(
                or_(
                    Candidate.organization_id == org_id,
                    Candidate.org_id == org_id,
                ),
                Candidate.is_deleted.is_(False),
                Candidate.is_merged.is_(False),
            )
        )
        if exclude_id is not None:
            stmt = stmt.where(Candidate.id != exclude_id)
        return list(db.scalars(stmt))

    def _build_match(
        self,
        candidate: Candidate,
        db: Session,
        *,
        confidence: float,
        match_type: str,
    ) -> DuplicateMatch:
        from sqlalchemy import func as sa_func

        try:
            pipeline_count: int = db.scalar(
                select(sa_func.count()).select_from(Pipeline).where(
                    Pipeline.candidate_id == candidate.id
                )
            ) or 0
        except Exception:
            pipeline_count = 0

        return DuplicateMatch(
            candidate_id=str(candidate.id),
            first_name=candidate.first_name,
            last_name=candidate.last_name,
            email=candidate.email or "",
            phone=candidate.phone,
            location=candidate.location,
            pipeline_count=pipeline_count,
            confidence=confidence,
            match_type=match_type,
        )
