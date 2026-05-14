"""AI evaluation of candidate answers.

Evaluates each answer independently on:
  - technical quality (for technical questions)
  - communication clarity
  - confidence / certainty
  - relevance to the question
  - role alignment
  - depth of understanding

Returns structured per-answer scores and qualitative feedback.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.ai.openai_client import AIResponse, OpenAIClient, OpenAIUnavailableError

logger = logging.getLogger(__name__)

# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert technical interviewer and screening evaluator for an enterprise ATS.
Your task: evaluate a candidate's answer to a screening question.

RULES:
- Return ONLY valid JSON — no prose, no markdown fences.
- Be objective, fair, and constructive.
- Scores are 0–10 integers (10 = exceptional, 0 = no answer / irrelevant).
- Confidence reflects how certain you are in your own evaluation (0–100).
- Strengths and concerns are short bullet strings (max 4 each).

OUTPUT FORMAT:
{
  "ai_score": <0-10>,
  "communication_rating": <0-10>,
  "technical_rating": <0-10>,
  "strengths": ["<strength1>", "<strength2>"],
  "concerns": ["<concern1>", "<concern2>"],
  "reasoning": "<2-3 sentence recruiter-friendly explanation of the score>",
  "follow_up_suggestion": "<optional: specific follow-up question worth asking in a human interview>",
  "confidence": <0-100>
}"""


def _build_user_prompt(
    *,
    job_title: str,
    question_text: str,
    question_category: str,
    expected_signals: dict | None,
    answer_text: str,
) -> str:
    signals_str = ""
    if expected_signals:
        concepts = expected_signals.get("key_concepts", [])
        red_flags = expected_signals.get("red_flags", [])
        ideal = expected_signals.get("ideal_depth", "")
        if concepts:
            signals_str += f"\nExpected key concepts: {', '.join(concepts)}"
        if red_flags:
            signals_str += f"\nRed flags to watch: {', '.join(red_flags)}"
        if ideal:
            signals_str += f"\nIdeal answer depth: {ideal}"

    return f"""JOB TITLE: {job_title}
QUESTION CATEGORY: {question_category}
{signals_str}

QUESTION: {question_text}

CANDIDATE ANSWER:
{answer_text[:3000]}

Evaluate this answer. Consider:
- Is it relevant and directly addresses the question?
- Does it demonstrate appropriate depth for a {question_category} question?
- Is the communication clear and structured?
- For technical questions: does it show real understanding or surface-level knowledge?
- Are there concerning gaps or evasions?"""


# ── Dataclass output ──────────────────────────────────────────────────────────

@dataclass
class AnswerEvaluation:
    ai_score: int
    communication_rating: int
    technical_rating: int
    strengths: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    reasoning: str = ""
    follow_up_suggestion: str | None = None
    confidence: int = 50
    fallback_used: bool = False
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""


# ── Evaluator ────────────────────────────────────────────────────────────────

class AnswerEvaluator:
    """Evaluates a single candidate answer via OpenAI."""

    def __init__(self, client: OpenAIClient | None = None) -> None:
        self._client = client or OpenAIClient()

    def evaluate(
        self,
        *,
        job_title: str,
        question_text: str,
        question_category: str,
        expected_signals: dict | None,
        answer_text: str,
    ) -> AnswerEvaluation:
        """Evaluate one answer. Returns a fallback evaluation on AI failure."""

        if not self._client.is_configured():
            logger.warning("answer_evaluator.openai_not_configured — using fallback")
            return self._fallback()

        user_prompt = _build_user_prompt(
            job_title=job_title,
            question_text=question_text,
            question_category=question_category,
            expected_signals=expected_signals,
            answer_text=answer_text,
        )

        try:
            response: AIResponse = self._client.chat_json(
                system=_SYSTEM_PROMPT,
                user=user_prompt,
                temperature=0.15,
                max_tokens=1024,
            )
            data = response.parse_json()
            return self._parse(data, response)

        except OpenAIUnavailableError as exc:
            logger.warning("answer_evaluator.ai_unavailable: %s", exc)
            return self._fallback()

        except Exception as exc:
            logger.exception("answer_evaluator.unexpected_error: %s", exc)
            return self._fallback()

    @staticmethod
    def _parse(data: Any, response: AIResponse) -> AnswerEvaluation:
        def _clamp_int(v: Any, lo: int, hi: int, default: int) -> int:
            try:
                return max(lo, min(hi, int(v)))
            except (TypeError, ValueError):
                return default

        return AnswerEvaluation(
            ai_score=_clamp_int(data.get("ai_score"), 0, 10, 5),
            communication_rating=_clamp_int(data.get("communication_rating"), 0, 10, 5),
            technical_rating=_clamp_int(data.get("technical_rating"), 0, 10, 5),
            strengths=[str(s) for s in (data.get("strengths") or [])[:4]],
            concerns=[str(c) for c in (data.get("concerns") or [])[:4]],
            reasoning=str(data.get("reasoning") or "")[:2000],
            follow_up_suggestion=str(data.get("follow_up_suggestion") or "")[:500] or None,
            confidence=_clamp_int(data.get("confidence"), 0, 100, 50),
            fallback_used=False,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            model=response.model,
        )

    @staticmethod
    def _fallback() -> AnswerEvaluation:
        return AnswerEvaluation(
            ai_score=5,
            communication_rating=5,
            technical_rating=5,
            strengths=["Answer provided"],
            concerns=["AI evaluation unavailable — manual review required"],
            reasoning="Automated evaluation was not available. Please review this answer manually.",
            follow_up_suggestion=None,
            confidence=0,
            fallback_used=True,
            model="fallback",
        )
