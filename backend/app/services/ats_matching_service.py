"""ATS Matching Service.

Compares one candidate's structured profile against one job's normalized
requirements and produces a deterministic match score breakdown.

Weights (from spec):
- Required skills:  50%
- Preferred skills: 20%
- Experience match: 15%
- Title similarity: 10%
- Education match:   5%
                  -------
                   100%

Tiers:
- 85+      -> Strong Match
- 70..84   -> Good Match
- 50..69   -> Moderate Match
- <50      -> Weak Match

Output is intentionally serializable (dict-friendly) so the matching service
can be reused by both:
- the live API (`GET /jobs/{id}/matches`) which returns it as JSON, and
- the persistence layer (`candidate_job_matches.matched_skills/missing_skills/
  category_scores`) which stores it as JSONB.

The service is stateless. Pass in pre-loaded structured fields (skills,
years, education, etc.) so this stays unit-testable and so the caller can
batch-load candidates without N+1 DB calls.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Iterable

from app.services.jd_normalization_service import JDNormalizationService

logger = logging.getLogger(__name__)


# Public so the persistence layer can use the same constants.
WEIGHT_REQUIRED_SKILLS = 50
WEIGHT_PREFERRED_SKILLS = 20
WEIGHT_EXPERIENCE = 15
WEIGHT_TITLE = 10
WEIGHT_EDUCATION = 5
TOTAL_WEIGHT = (
    WEIGHT_REQUIRED_SKILLS
    + WEIGHT_PREFERRED_SKILLS
    + WEIGHT_EXPERIENCE
    + WEIGHT_TITLE
    + WEIGHT_EDUCATION
)
assert TOTAL_WEIGHT == 100, "ATS scoring weights must sum to 100."


# Education ranks. Higher rank = higher degree. Used to determine whether
# the candidate meets/exceeds the JD's stated minimum education.
_EDU_LEVELS: tuple[tuple[str, int], ...] = (
    ("phd", 5),
    ("ph.d", 5),
    ("doctorate", 5),
    ("mba", 4),
    ("m.b.a", 4),
    ("master", 4),
    ("msc", 4),
    ("m.sc", 4),
    ("m.s.", 4),
    ("ms ", 4),
    ("bachelor", 3),
    ("btech", 3),
    ("b.tech", 3),
    ("bsc", 3),
    ("b.sc", 3),
    ("b.s.", 3),
    ("diploma", 2),
    ("associate", 2),
    ("high school", 1),
)


@dataclass(slots=True)
class CandidateScoringInput:
    """Pre-loaded candidate fields used for scoring.

    Note: skills are expected pre-normalized (lowercased + alias-mapped via
    `JDNormalizationService.normalize_skill`). The matching service does not
    re-normalize what the caller supplies.
    """

    candidate_id: str
    skills: list[str] = field(default_factory=list)
    years_of_experience: float | None = None
    previous_titles: list[str] = field(default_factory=list)
    education: list[str] = field(default_factory=list)
    parser_confidence: float | None = None  # from extraction service [0..1]


@dataclass(slots=True)
class JobScoringInput:
    """Pre-loaded job fields used for scoring.

    `required_skills_normalized` and `preferred_skills_normalized` come from
    `JDNormalizationService.normalize`. `min_experience_years` is the lower
    bound from the JD; `max_experience_years` is informational only (we don't
    penalize over-qualified candidates here).
    """

    job_id: str
    title: str | None = None
    required_skills_normalized: list[str] = field(default_factory=list)
    preferred_skills_normalized: list[str] = field(default_factory=list)
    min_experience_years: float | None = None
    max_experience_years: float | None = None
    education_requirements: list[str] = field(default_factory=list)


@dataclass(slots=True)
class MatchResult:
    """Deterministic scoring output for a (candidate, job) pair."""

    match_score: int  # 0..100
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    matched_preferred_skills: list[str] = field(default_factory=list)
    category_scores: dict[str, int] = field(default_factory=dict)
    recommendation: str = "Weak Match"
    confidence_score: float = 0.0

    def to_jsonable(self) -> dict[str, object]:
        """Return a JSON-serializable view safe to drop into JSONB columns."""
        return {
            "match_score": self.match_score,
            "matched_skills": list(self.matched_skills),
            "missing_skills": list(self.missing_skills),
            "matched_preferred_skills": list(self.matched_preferred_skills),
            "category_scores": dict(self.category_scores),
            "recommendation": self.recommendation,
            "confidence_score": float(self.confidence_score),
        }


class ATSMatchingService:
    """Deterministic, weighted candidate-job matcher."""

    def __init__(self) -> None:
        # Stateless, but we cache the normalizer instance for a tiny perf win
        # in batched scoring loops.
        self._normalizer = JDNormalizationService()

    def score(self, *, candidate: CandidateScoringInput, job: JobScoringInput) -> MatchResult:
        # Normalize everything one more time defensively. If the caller
        # already normalized, this is a no-op; if not, it keeps scoring sound.
        cand_skills = {self._normalizer.normalize_skill(s) for s in candidate.skills if s}
        cand_skills.discard("")
        required = [s for s in (self._normalizer.normalize_skill(x) for x in job.required_skills_normalized) if s]
        preferred = [s for s in (self._normalizer.normalize_skill(x) for x in job.preferred_skills_normalized) if s]

        required_score, matched_required, missing_required = self._score_required(cand_skills, required)
        preferred_score, matched_preferred = self._score_preferred(cand_skills, preferred)
        experience_score = self._score_experience(candidate.years_of_experience, job)
        title_score = self._score_title(candidate.previous_titles, job.title)
        education_score = self._score_education(candidate.education, job.education_requirements)

        weighted = (
            required_score * WEIGHT_REQUIRED_SKILLS
            + preferred_score * WEIGHT_PREFERRED_SKILLS
            + experience_score * WEIGHT_EXPERIENCE
            + title_score * WEIGHT_TITLE
            + education_score * WEIGHT_EDUCATION
        ) / 100.0
        match_score = int(round(max(0.0, min(100.0, weighted)) * 1.0))
        recommendation = self._tier_for(match_score)

        confidence_score = self._compute_confidence(
            candidate=candidate,
            job=job,
            required_count=len(required),
            preferred_count=len(preferred),
            matched_required=len(matched_required),
        )

        category_scores = {
            "required_skills": int(round(required_score)),
            "preferred_skills": int(round(preferred_score)),
            "experience": int(round(experience_score)),
            "title": int(round(title_score)),
            "education": int(round(education_score)),
        }

        return MatchResult(
            match_score=match_score,
            matched_skills=sorted(matched_required),
            missing_skills=sorted(missing_required),
            matched_preferred_skills=sorted(matched_preferred),
            category_scores=category_scores,
            recommendation=recommendation,
            confidence_score=round(confidence_score, 3),
        )

    # ------------------------------------------------------------------
    # Scoring helpers (each returns a 0..100 sub-score)
    # ------------------------------------------------------------------
    @staticmethod
    def _score_required(
        candidate_skills: set[str], required: Iterable[str]
    ) -> tuple[float, list[str], list[str]]:
        required_list = list(required)
        # An open JD with no required skills should not block strong candidates.
        # Treat as full credit and report no missing skills.
        if not required_list:
            return 100.0, [], []
        matched: list[str] = []
        missing: list[str] = []
        for skill in required_list:
            if skill in candidate_skills:
                matched.append(skill)
            else:
                missing.append(skill)
        score = (len(matched) / len(required_list)) * 100.0
        return score, matched, missing

    @staticmethod
    def _score_preferred(
        candidate_skills: set[str], preferred: Iterable[str]
    ) -> tuple[float, list[str]]:
        preferred_list = list(preferred)
        if not preferred_list:
            # Missing preferred list is not a penalty; it's just absent.
            return 100.0, []
        matched = [skill for skill in preferred_list if skill in candidate_skills]
        score = (len(matched) / len(preferred_list)) * 100.0
        return score, matched

    @staticmethod
    def _score_experience(years: float | None, job: JobScoringInput) -> float:
        # No requirement on the JD: full credit if the candidate has any
        # experience info, neutral 70 otherwise so we don't unfairly cap.
        if job.min_experience_years is None:
            return 100.0 if years is not None else 70.0
        if years is None:
            return 0.0
        if years >= job.min_experience_years:
            # Tiny boost for exceeding the floor by 1+ years (capped at 100).
            over = years - job.min_experience_years
            return min(100.0, 90.0 + over * 1.0)
        # Linear ramp from 0..90 across the [0, min_experience] range.
        ratio = max(0.0, years / max(job.min_experience_years, 0.1))
        return round(ratio * 90.0, 2)

    @classmethod
    def _score_title(cls, previous_titles: Iterable[str], jd_title: str | None) -> float:
        if not jd_title:
            return 100.0  # No title in JD → don't penalize.
        jd_tokens = cls._title_tokens(jd_title)
        if not jd_tokens:
            return 100.0
        best = 0.0
        for raw_title in previous_titles:
            cand_tokens = cls._title_tokens(raw_title)
            if not cand_tokens:
                continue
            overlap = len(jd_tokens & cand_tokens)
            score = (overlap / len(jd_tokens)) * 100.0
            if score > best:
                best = score
        return best

    @staticmethod
    def _title_tokens(value: str) -> set[str]:
        # Strip seniority adjectives so "Senior Backend Engineer" matches
        # "Backend Engineer" with high overlap. Keep the role nouns.
        stop = {"senior", "sr", "junior", "jr", "lead", "principal", "staff", "the", "a", "an", "of", "and"}
        tokens = re.findall(r"[a-zA-Z][a-zA-Z+#.]+", value.lower())
        return {tok for tok in tokens if tok not in stop and len(tok) >= 2}

    @classmethod
    def _score_education(
        cls, candidate_education: Iterable[str], jd_education_requirements: Iterable[str]
    ) -> float:
        jd_rank = max((cls._edu_rank(req) for req in jd_education_requirements), default=0)
        if jd_rank == 0:
            # No formal requirement; reward having any degree.
            cand_rank = max((cls._edu_rank(line) for line in candidate_education), default=0)
            return 100.0 if cand_rank > 0 else 80.0
        cand_rank = max((cls._edu_rank(line) for line in candidate_education), default=0)
        if cand_rank == 0:
            return 0.0
        if cand_rank >= jd_rank:
            return 100.0
        # Each missing rank is a 25-point hit, floored at 0.
        return max(0.0, 100.0 - (jd_rank - cand_rank) * 25.0)

    @staticmethod
    def _edu_rank(text: str | None) -> int:
        if not text:
            return 0
        text_l = text.lower()
        for keyword, rank in _EDU_LEVELS:
            if keyword in text_l:
                return rank
        return 0

    @staticmethod
    def _tier_for(score: int) -> str:
        if score >= 85:
            return "Strong Match"
        if score >= 70:
            return "Good Match"
        if score >= 50:
            return "Moderate Match"
        return "Weak Match"

    @staticmethod
    def _compute_confidence(
        *,
        candidate: CandidateScoringInput,
        job: JobScoringInput,
        required_count: int,
        preferred_count: int,
        matched_required: int,
    ) -> float:
        """Confidence = (extraction coverage) * (job specificity) * (signal density).

        - Extraction coverage uses the parser confidence if available, else
          a coarse coverage on candidate fields.
        - Job specificity rewards JDs that actually list required skills.
        - Signal density rewards matches over a tiny job (avoids 100/100 from
          a JD with one required skill and one match).
        """
        # Extraction coverage
        if candidate.parser_confidence is not None:
            coverage = max(0.0, min(1.0, candidate.parser_confidence))
        else:
            populated = sum(
                1
                for v in (
                    candidate.skills,
                    candidate.previous_titles,
                    candidate.education,
                )
                if v
            )
            coverage = populated / 3.0
            if candidate.years_of_experience is not None:
                coverage = min(1.0, coverage + 0.2)

        # Job specificity
        specificity = 0.6
        if required_count >= 3:
            specificity = 1.0
        elif required_count >= 1:
            specificity = 0.8

        # Signal density
        if required_count == 0:
            density = 0.7
        else:
            density = 0.6 + 0.4 * (matched_required / required_count)

        return round(coverage * specificity * density, 3)
