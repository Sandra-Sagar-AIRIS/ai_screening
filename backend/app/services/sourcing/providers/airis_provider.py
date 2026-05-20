"""AIRIS internal candidate search provider.

Uses the pg_trgm GIN index (migration 20260519_0002) for fast text search
across candidate experience_summary and notes fields.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.services.sourcing.providers.base import BaseCandidateProvider, RawCandidate, SourcingQuery

logger = logging.getLogger(__name__)


class AirisCandidateProvider(BaseCandidateProvider):
    provider_id = "airis"

    def __init__(self, db: Session) -> None:
        self._db = db

    async def search(
        self,
        query: SourcingQuery,
        org_id: UUID,
        limit: int = 20,
    ) -> list[RawCandidate]:
        search_terms = list(query.skills) + [query.title] + list(query.keywords)
        search_str = " ".join(filter(None, search_terms)).strip()
        if not search_str:
            logger.warning("airis_provider.empty_search_query", extra={"org_id": str(org_id)})
            return []

        try:
            # Full-text trigram search across experience_summary + notes
            stmt = (
                select(Candidate)
                .where(
                    or_(
                        Candidate.organization_id == org_id,
                        Candidate.org_id == org_id,
                    ),
                    Candidate.is_deleted.is_(False),
                    Candidate.deleted_at.is_(None),
                )
                .order_by(
                    text(
                        "similarity(coalesce(experience_summary,'') || ' ' || coalesce(notes,''), :q) DESC"
                    ).bindparams(q=search_str)
                )
                .limit(limit)
            )
            rows: list[Candidate] = list(self._db.scalars(stmt).all())
        except Exception:
            logger.exception(
                "airis_provider.search_failed",
                extra={"org_id": str(org_id), "search_str": search_str[:200]},
            )
            return []

        results: list[RawCandidate] = []
        for c in rows:
            skills: list[str] = []
            if c.experience_summary:
                # Best-effort: extract comma-separated skill tokens from experience_summary
                skills = [s.strip() for s in c.experience_summary.split(",") if s.strip()][:10]

            results.append(
                RawCandidate(
                    source=self.provider_id,
                    external_id=str(c.id),
                    first_name=c.first_name,
                    last_name=c.last_name,
                    email=c.email,
                    phone=c.phone,
                    location=c.location,
                    title=None,
                    skills=skills,
                    raw_data={"candidate_id": str(c.id), "notes": c.notes or ""},
                )
            )
        logger.info(
            "airis_provider.search_complete",
            extra={"org_id": str(org_id), "result_count": len(results)},
        )
        return results
