"""Candidate Import Service.

Converts a SourcingResult into a permanent Candidate record,
deduplicating against existing records first.
"""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.candidate import Candidate
from app.models.sourcing_session import SourcingResult
from app.schemas.candidate import CandidateCreate

logger = logging.getLogger(__name__)


class CandidateImportService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def import_result(
        self,
        result: SourcingResult,
        org_id: UUID,
        imported_by: UUID,
    ) -> Candidate:
        """Return existing or newly-created Candidate for *result*.

        If a candidate with the same email already exists in this org,
        return it and update the result's candidate_id.
        """
        # ── Check for existing candidate by email ─────────────────────────────
        if result.email:
            existing = self._db.scalar(
                select(Candidate).where(
                    or_(
                        Candidate.organization_id == org_id,
                        Candidate.org_id == org_id,
                    ),
                    Candidate.email == result.email.lower(),
                    Candidate.is_deleted.is_(False),
                )
            )
            if existing:
                logger.info(
                    "sourcing.importer.found_existing",
                    extra={
                        "candidate_id": str(existing.id),
                        "org_id": str(org_id),
                        "result_id": str(result.id),
                    },
                )
                result.candidate_id = existing.id
                return existing

        # ── Create new candidate ──────────────────────────────────────────────
        source_type = "internal" if result.source == "airis" else "vendor"
        skills_str = ", ".join(result.skills or [])
        title_str = result.title or ""
        experience_summary = f"{skills_str} | {title_str}".strip(" |") if (skills_str or title_str) else None

        candidate = Candidate(
            organization_id=org_id,
            first_name=(result.first_name or "Unknown").strip(),
            last_name=(result.last_name or "").strip(),
            email=result.email.lower() if result.email else f"unknown-{result.id}@sourced.invalid",
            phone=result.phone,
            location=result.location,
            experience_summary=experience_summary,
            notes=f"Sourced via AI sourcing session {result.session_id}",
            created_by=imported_by,
            source_type=source_type,
        )
        self._db.add(candidate)
        self._db.flush()
        self._db.refresh(candidate)

        result.candidate_id = candidate.id
        logger.info(
            "sourcing.importer.created",
            extra={
                "candidate_id": str(candidate.id),
                "org_id": str(org_id),
                "result_id": str(result.id),
                "source_type": source_type,
            },
        )
        return candidate
