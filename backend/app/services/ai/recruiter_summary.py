"""Generates a recruiter-facing AI summary after all answers are evaluated.

The summary is written for a non-technical recruiter: plain English, structured,
actionable. It synthesises scores, patterns in strengths/concerns, and
recommends focus areas for any follow-up human interview.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from app.services.ai.openai_client import AIResponse, OpenAIClient, OpenAIUnavailableError

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a senior talent acquisition advisor synthesising a candidate AI pre-screening result.
Your audience: a recruiter who will decide whether to advance this candidate.

RULES:
- Return ONLY valid JSON — no prose, no markdown fences.
- Write for a non-technical recruiter; avoid jargon.
- Be balanced: acknowledge strengths AND concerns.
- The recommendation is advisory only — the recruiter makes the final decision.
- Keep each text field concise (2-4 sentences max).

OUTPUT FORMAT:
{
  "overall_assessment": "<2-3 sentence plain-English overview of the candidate's performance>",
  "key_strengths": ["<strength1>", "<strength2>", "<strength3>"],
  "key_concerns": ["<concern1>", "<concern2>"],
  "recommendation_reasoning": "<1-2 sentences explaining why you're making this recommendation>",
  "follow_up_focus_areas": ["<area to probe in human interview>", "<area2>"],
  "hiring_signal": "<one of: strong_proceed|proceed|needs_manual_review|weak_match|reject_recommendation>"
}"""


def _build_user_prompt(
    *,
    candidate_name: str,
    job_title: str,
    screening_type: str,
    questions_and_evaluations: list[dict],
    aggregate_scores: dict,
) -> str:
    qa_summary = []
    for i, item in enumerate(questions_and_evaluations[:10], 1):
        q = item.get("question", "")
        score = item.get("ai_score", "?")
        strengths = ", ".join(item.get("strengths", [])[:2])
        concerns = ", ".join(item.get("concerns", [])[:2])
        qa_summary.append(
            f"Q{i} [{item.get('category', '')}]: {q[:120]}\n"
            f"  Score: {score}/10 | Strengths: {strengths or 'none'} | Concerns: {concerns or 'none'}"
        )

    return f"""Candidate: {candidate_name}
Role: {job_title}
Screening type: {screening_type}

AGGREGATE SCORES:
- Overall: {aggregate_scores.get('overall', 'N/A')}/100
- Technical: {aggregate_scores.get('technical', 'N/A')}/100
- Communication: {aggregate_scores.get('communication', 'N/A')}/100
- Confidence: {aggregate_scores.get('confidence', 'N/A')}/100

QUESTION-BY-QUESTION SUMMARY:
{chr(10).join(qa_summary)}

Write a concise recruiter summary and provide a hiring signal recommendation."""


@dataclass
class RecruiterSummaryResult:
    overall_assessment: str
    key_strengths: list[str]
    key_concerns: list[str]
    recommendation_reasoning: str
    follow_up_focus_areas: list[str]
    hiring_signal: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    fallback_used: bool = False


class RecruiterSummaryGenerator:
    """Generates the final recruiter-facing AI summary."""

    def __init__(self, client: OpenAIClient | None = None) -> None:
        self._client = client or OpenAIClient()

    def generate(
        self,
        *,
        candidate_name: str,
        job_title: str,
        screening_type: str,
        questions_and_evaluations: list[dict],
        aggregate_scores: dict,
    ) -> RecruiterSummaryResult:
        if not self._client.is_configured():
            return self._fallback()

        user_prompt = _build_user_prompt(
            candidate_name=candidate_name,
            job_title=job_title,
            screening_type=screening_type,
            questions_and_evaluations=questions_and_evaluations,
            aggregate_scores=aggregate_scores,
        )

        try:
            response: AIResponse = self._client.chat_json(
                system=_SYSTEM_PROMPT,
                user=user_prompt,
                temperature=0.25,
                max_tokens=1200,
            )
            data = response.parse_json()
            valid_signals = {
                "strong_proceed", "proceed", "needs_manual_review",
                "weak_match", "reject_recommendation",
            }
            signal = data.get("hiring_signal", "needs_manual_review")
            if signal not in valid_signals:
                signal = "needs_manual_review"

            return RecruiterSummaryResult(
                overall_assessment=str(data.get("overall_assessment") or "")[:1000],
                key_strengths=[str(s) for s in (data.get("key_strengths") or [])[:5]],
                key_concerns=[str(c) for c in (data.get("key_concerns") or [])[:5]],
                recommendation_reasoning=str(data.get("recommendation_reasoning") or "")[:500],
                follow_up_focus_areas=[str(a) for a in (data.get("follow_up_focus_areas") or [])[:5]],
                hiring_signal=signal,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                model=response.model,
            )

        except (OpenAIUnavailableError, Exception) as exc:
            logger.warning("recruiter_summary.failed: %s", exc)
            return self._fallback()

    @staticmethod
    def _fallback() -> RecruiterSummaryResult:
        return RecruiterSummaryResult(
            overall_assessment="AI summary generation was unavailable. Please review individual question scores manually.",
            key_strengths=["Screening questions answered"],
            key_concerns=["AI evaluation unavailable"],
            recommendation_reasoning="Manual review is required as AI evaluation could not complete.",
            follow_up_focus_areas=["Review answers manually before making a decision"],
            hiring_signal="needs_manual_review",
            model="fallback",
            fallback_used=True,
        )
