"""Recommendation engine — converts aggregate scores into a final recommendation.

Operates purely on computed scores (no extra AI call needed). The output is
always advisory: recruiters make the final decision.

Score thresholds are intentionally conservative to avoid false rejects.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RecommendationResult:
    recommendation: str       # ScreeningRecommendation enum value
    overall_score: float      # 0–100
    communication_score: float
    technical_score: float
    confidence_score: float


def compute_scores_and_recommendation(
    *,
    evaluations: list[dict],
    screening_type: str,
) -> RecommendationResult:
    """Compute aggregate scores from per-answer evaluations and derive recommendation.

    evaluations: list of dicts with keys:
        ai_score (0-10), communication_rating (0-10), technical_rating (0-10), confidence (0-100)
    """
    if not evaluations:
        return RecommendationResult(
            recommendation="needs_manual_review",
            overall_score=0.0,
            communication_score=0.0,
            technical_score=0.0,
            confidence_score=0.0,
        )

    n = len(evaluations)

    # Normalise per-answer scores to 0-100
    ai_scores = [min(100.0, max(0.0, e.get("ai_score", 5) * 10.0)) for e in evaluations]
    comm_scores = [min(100.0, max(0.0, e.get("communication_rating", 5) * 10.0)) for e in evaluations]
    tech_scores = [min(100.0, max(0.0, e.get("technical_rating", 5) * 10.0)) for e in evaluations]
    conf_scores = [min(100.0, max(0.0, float(e.get("confidence", 50)))) for e in evaluations]

    avg_ai = sum(ai_scores) / n
    avg_comm = sum(comm_scores) / n
    avg_tech = sum(tech_scores) / n
    avg_conf = sum(conf_scores) / n

    # Weight overall score by screening type
    if screening_type == "technical":
        overall = avg_ai * 0.45 + avg_tech * 0.35 + avg_comm * 0.20
    elif screening_type in ("hr", "behavioral", "communication"):
        overall = avg_ai * 0.35 + avg_comm * 0.45 + avg_tech * 0.20
    elif screening_type == "leadership":
        overall = avg_ai * 0.40 + avg_comm * 0.35 + avg_tech * 0.25
    else:  # role_fit
        overall = avg_ai * 0.40 + avg_comm * 0.30 + avg_tech * 0.30

    recommendation = _score_to_recommendation(overall, avg_conf)

    return RecommendationResult(
        recommendation=recommendation,
        overall_score=round(overall, 2),
        communication_score=round(avg_comm, 2),
        technical_score=round(avg_tech, 2),
        confidence_score=round(avg_conf, 2),
    )


def _score_to_recommendation(overall: float, confidence: float) -> str:
    """Map a 0-100 overall score to a recommendation string.

    Confidence below 40 forces needs_manual_review regardless of score.
    """
    if confidence < 40:
        return "needs_manual_review"

    if overall >= 78:
        return "strong_proceed"
    elif overall >= 62:
        return "proceed"
    elif overall >= 48:
        return "needs_manual_review"
    elif overall >= 32:
        return "weak_match"
    else:
        return "reject_recommendation"
