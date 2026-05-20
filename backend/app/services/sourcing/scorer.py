"""AI Relevance Scoring Integration.

Scores each RawCandidate using the existing ATS (deterministic) + Grok semantic pipeline.
Runs up to 5 concurrent Grok calls; individual failures do not abort the batch.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from app.services.sourcing.providers.base import RawCandidate

logger = logging.getLogger(__name__)

_MAX_CONCURRENT_GROK = 5
_GROK_TIMEOUT_S = 10.0


@dataclass
class ScoredCandidate:
    """RawCandidate with scoring fields appended."""

    raw: RawCandidate
    ats_score: float | None = None
    ats_tier: str | None = None
    semantic_score: float | None = None
    recruiter_summary: str | None = None
    matched_skills: list[str] = field(default_factory=list)

    # Delegate attribute access to raw for convenience
    @property
    def source(self) -> str:
        return self.raw.source

    @property
    def external_id(self) -> str | None:
        return self.raw.external_id

    @property
    def first_name(self) -> str:
        return self.raw.first_name

    @property
    def last_name(self) -> str:
        return self.raw.last_name

    @property
    def email(self) -> str | None:
        return self.raw.email

    @property
    def phone(self) -> str | None:
        return self.raw.phone

    @property
    def location(self) -> str | None:
        return self.raw.location

    @property
    def title(self) -> str | None:
        return self.raw.title

    @property
    def skills(self) -> list[str]:
        return self.raw.skills

    @property
    def is_duplicate(self) -> bool:
        return self.raw.is_duplicate

    @property
    def raw_data(self) -> dict:
        return self.raw.raw_data


def _ats_tier(score: float) -> str:
    if score >= 85:
        return "Strong"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Moderate"
    return "Weak"


class CandidateScoringService:
    """Score a batch of RawCandidates against a JD."""

    def __init__(self, jd_text: str) -> None:
        self._jd_text = jd_text
        self._sem = asyncio.Semaphore(_MAX_CONCURRENT_GROK)

    async def score_batch(self, candidates: list[RawCandidate]) -> list[ScoredCandidate]:
        """Score all candidates, returning one ScoredCandidate per input."""
        tasks = [self._score_one(c) for c in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        out: list[ScoredCandidate] = []
        for c, result in zip(candidates, results):
            if isinstance(result, Exception):
                logger.warning(
                    "scorer.candidate_failed",
                    extra={"source": c.source, "external_id": c.external_id, "error": str(result)},
                )
                out.append(ScoredCandidate(raw=c))
            else:
                out.append(result)  # type: ignore[arg-type]
        return out

    async def _score_one(self, raw: RawCandidate) -> ScoredCandidate:
        scored = ScoredCandidate(raw=raw)

        # ── Deterministic ATS score ───────────────────────────────────────────
        try:
            from app.services.ats_matching_service import ATSMatchingService, CandidateScoringInput, JobScoringInput
            from app.services.jd_normalization_service import JDNormalizationService

            normalizer = JDNormalizationService()
            # Extract skills from JD text heuristically
            jd_skills = [w for w in self._jd_text.split() if len(w) > 2][:20]
            jd_norm = normalizer.normalize(required_skills=jd_skills)

            cand_input = CandidateScoringInput(
                candidate_id=raw.external_id or "unknown",
                skills=raw.skills or [],
                years_of_experience=float(raw.experience_years) if raw.experience_years else None,
                previous_titles=[raw.title] if raw.title else [],
            )
            job_input = JobScoringInput(
                job_id="sourcing",
                title=None,
                required_skills_normalized=jd_norm.required_skills_normalized,
                preferred_skills_normalized=jd_norm.preferred_skills_normalized,
            )
            service = ATSMatchingService()
            result = service.score(candidate=cand_input, job=job_input)
            scored.ats_score = float(result.match_score)
            scored.ats_tier = result.recommendation
            scored.matched_skills = result.matched_skills
        except Exception:
            logger.warning(
                "scorer.ats_score_failed",
                exc_info=True,
                extra={"source": raw.source, "external_id": raw.external_id},
            )

        # ── Grok semantic enrichment ──────────────────────────────────────────
        try:
            async with self._sem:
                semantic = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, self._run_semantic, raw, scored
                    ),
                    timeout=_GROK_TIMEOUT_S,
                )
            if semantic:
                scored.semantic_score = float(semantic.get("semantic_match_score", 0))
                scored.recruiter_summary = semantic.get("recruiter_summary", "")
                if not scored.matched_skills:
                    scored.matched_skills = semantic.get("semantic_skill_matches", [])
        except asyncio.TimeoutError:
            logger.warning(
                "scorer.semantic_timeout",
                extra={"source": raw.source, "external_id": raw.external_id},
            )
        except Exception:
            logger.warning(
                "scorer.semantic_failed",
                exc_info=True,
                extra={"source": raw.source, "external_id": raw.external_id},
            )

        return scored

    def _run_semantic(self, raw: RawCandidate, scored: ScoredCandidate) -> dict | None:
        """Blocking Grok call — runs in thread executor."""
        try:
            from app.services.semantic_matching_service import (
                SemanticMatchingService,
                build_condensed_candidate_job_payload,
            )
            from app.services.jd_normalization_service import JDNormalizationService

            normalizer = JDNormalizationService()
            jd_skills = [w for w in self._jd_text.split() if len(w) > 2][:20]
            jd_norm = normalizer.normalize(required_skills=jd_skills)

            condensed = build_condensed_candidate_job_payload(
                candidate_skills=raw.skills or [],
                candidate_titles=[raw.title] if raw.title else [],
                years_experience=float(raw.experience_years) if raw.experience_years else None,
                education=[],
                certifications=[],
                experience_summary=None,
                job_title=None,
                job_summary=self._jd_text[:800],
                job_required_skills=jd_norm.required_skills_normalized,
                job_preferred_skills=jd_norm.preferred_skills_normalized,
                deterministic_score=int(scored.ats_score or 0),
                deterministic_matched=scored.matched_skills or [],
                deterministic_missing=[],
            )
            svc = SemanticMatchingService()
            result = svc.enrich_pair(condensed)
            if result and result.payload:
                return {
                    "semantic_match_score": result.payload.semantic_match_score,
                    "recruiter_summary": result.payload.recruiter_summary,
                    "semantic_skill_matches": result.payload.semantic_skill_matches,
                }
            return None
        except Exception:
            logger.warning("scorer.semantic_enrich_failed", exc_info=True)
            return None
