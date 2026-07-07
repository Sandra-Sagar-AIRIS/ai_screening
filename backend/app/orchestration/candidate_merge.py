"""Orchestrates Candidate merge -> Pipeline/Interview reassignment (CAND-006).

CandidateMergeService used to construct and execute Pipeline/Interview
`update()` statements directly from the Candidate domain
(app/services/candidate_dedup/merge_service.py). Reassigning a duplicate
candidate's rows to the survivor is a Pipeline-domain concern and an
Interview-domain concern respectively, so each now goes through its owning
service — PipelineService.reassign_candidate / InterviewService.reassign_candidate
— instead. This module sits above both domains so neither service needs to
import the other, mirroring the other orchestration modules in this package.

Preserves CAND-006's original best-effort semantics: a failure reassigning
one domain is logged and does not prevent the other domain's reassignment,
or the rest of the merge (job matches, sourcing results, soft-delete), from
proceeding. CandidateMergeService.merge() still owns the transaction — this
function only flushes into it, matching the "caller commits" contract
documented on CandidateMergeService.merge.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.services.interview_service import InterviewService
from app.services.pipeline_service import PipelineService

logger = logging.getLogger(__name__)


def reassign_candidate_across_pipeline_and_interview(
    db: Session,
    *,
    from_candidate_id: UUID,
    to_candidate_id: UUID,
    organization_id: UUID,
) -> None:
    """Repoint Pipeline and Interview rows from a merged-away candidate to the survivor."""
    try:
        PipelineService(db).reassign_candidate(
            from_candidate_id=from_candidate_id,
            to_candidate_id=to_candidate_id,
            organization_id=organization_id,
        )
    except Exception:
        logger.warning("cand006.merge.pipeline_reassign_failed", exc_info=True)

    try:
        InterviewService(db).reassign_candidate(
            from_candidate_id=from_candidate_id,
            to_candidate_id=to_candidate_id,
            organization_id=organization_id,
        )
    except Exception:
        logger.warning("cand006.merge.interview_reassign_failed", exc_info=True)
