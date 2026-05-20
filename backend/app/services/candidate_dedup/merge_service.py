"""CAND-006: Candidate merge service.

Admin-only operation that consolidates a duplicate candidate into a survivor:

  1. Reassigns Pipeline rows:          candidate_id → survivor
  2. Reassigns Interview rows:         candidate_id → survivor
  3. Reassigns CandidateJobMatch rows: candidate_id → survivor
     (deduplicates by (job_id, org_id) to avoid unique-constraint violations)
  4. Reassigns SourcingResult rows:    candidate_id → survivor
  5. Soft-deletes the duplicate:       is_deleted=True, is_merged=True, merged_into_id=survivor

All operations are performed inside the caller's transaction — the caller is
responsible for commit/rollback.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.candidate import Candidate

logger = logging.getLogger(__name__)


class CandidateMergeService:
    """Merge a duplicate candidate into a survivor candidate."""

    def merge(
        self,
        *,
        survivor_id: UUID,
        duplicate_id: UUID,
        actor_id: UUID,
        org_id: UUID,
        db: Session,
    ) -> None:
        """Execute the merge.

        Raises
        ------
        HTTPException 404  if either candidate is not found in the organisation.
        HTTPException 400  if survivor == duplicate, or either is already merged/deleted.
        """
        if survivor_id == duplicate_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "MERGE_SAME_CANDIDATE", "message": "Survivor and duplicate must be different candidates."},
            )

        survivor = self._get_candidate(db, survivor_id, org_id)
        duplicate = self._get_candidate(db, duplicate_id, org_id)

        if duplicate.is_merged or duplicate.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "CANDIDATE_ALREADY_MERGED",
                    "message": "The duplicate candidate has already been merged or deleted.",
                },
            )

        logger.info(
            "cand006.merge.start",
            extra={
                "survivor_id": str(survivor_id),
                "duplicate_id": str(duplicate_id),
                "actor_id": str(actor_id),
                "org_id": str(org_id),
            },
        )

        # ── 1. Pipeline ───────────────────────────────────────────────────────
        self._reassign_pipelines(db, duplicate_id, survivor_id)

        # ── 2. Interviews ─────────────────────────────────────────────────────
        self._reassign_interviews(db, duplicate_id, survivor_id)

        # ── 3. CandidateJobMatch (unique constraint-aware) ────────────────────
        self._reassign_job_matches(db, duplicate_id, survivor_id, org_id)

        # ── 4. SourcingResult ─────────────────────────────────────────────────
        self._reassign_sourcing_results(db, duplicate_id, survivor_id)

        # ── 5. Soft-delete duplicate ──────────────────────────────────────────
        now = datetime.now(tz=timezone.utc)
        duplicate.is_deleted = True
        duplicate.deleted_at = now
        duplicate.is_merged = True
        duplicate.merged_into_id = survivor_id
        db.add(duplicate)
        db.flush()

        logger.info(
            "cand006.merge.complete",
            extra={
                "survivor_id": str(survivor_id),
                "duplicate_id": str(duplicate_id),
                "actor_id": str(actor_id),
            },
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_candidate(self, db: Session, candidate_id: UUID, org_id: UUID) -> Candidate:
        from sqlalchemy import or_

        candidate = db.scalar(
            select(Candidate).where(
                Candidate.id == candidate_id,
                or_(
                    Candidate.organization_id == org_id,
                    Candidate.org_id == org_id,
                ),
            )
        )
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Candidate {candidate_id} not found.",
            )
        return candidate

    def _reassign_pipelines(self, db: Session, from_id: UUID, to_id: UUID) -> None:
        try:
            from app.models.pipeline import Pipeline

            db.execute(
                update(Pipeline)
                .where(Pipeline.candidate_id == from_id)
                .values(candidate_id=to_id)
            )
        except Exception:
            logger.warning("cand006.merge.pipeline_reassign_failed", exc_info=True)

    def _reassign_interviews(self, db: Session, from_id: UUID, to_id: UUID) -> None:
        try:
            from app.models.interview import Interview

            db.execute(
                update(Interview)
                .where(Interview.candidate_id == from_id)
                .values(candidate_id=to_id)
            )
        except Exception:
            logger.warning("cand006.merge.interview_reassign_failed", exc_info=True)

    def _reassign_job_matches(
        self, db: Session, from_id: UUID, to_id: UUID, org_id: UUID
    ) -> None:
        """Reassign CandidateJobMatch rows, skipping pairs the survivor already has."""
        try:
            from app.models.candidate_job_match import CandidateJobMatch

            # Find job_ids the survivor already has a match for
            existing_job_ids = set(
                db.scalars(
                    select(CandidateJobMatch.job_id).where(
                        CandidateJobMatch.candidate_id == to_id,
                        CandidateJobMatch.organization_id == org_id,
                    )
                )
            )

            # Fetch duplicate's matches
            dup_matches = list(
                db.scalars(
                    select(CandidateJobMatch).where(
                        CandidateJobMatch.candidate_id == from_id,
                        CandidateJobMatch.organization_id == org_id,
                    )
                )
            )

            for match in dup_matches:
                if match.job_id in existing_job_ids:
                    # Survivor already has a match for this job — discard duplicate's
                    db.delete(match)
                else:
                    match.candidate_id = to_id
                    db.add(match)

            db.flush()
        except Exception:
            logger.warning("cand006.merge.job_match_reassign_failed", exc_info=True)

    def _reassign_sourcing_results(self, db: Session, from_id: UUID, to_id: UUID) -> None:
        try:
            from app.models.sourcing_session import SourcingResult

            db.execute(
                update(SourcingResult)
                .where(SourcingResult.candidate_id == from_id)
                .values(candidate_id=to_id)
            )
        except Exception:
            logger.warning("cand006.merge.sourcing_result_reassign_failed", exc_info=True)
