"""AI suggestion engine for the Interview Copilot layer.

Generates context-aware follow-up questions and post-interview summaries using
the existing OpenAIClient infrastructure.  All calls are synchronous and must
be dispatched via FastAPI BackgroundTasks so they never block request threads.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.services.ai.openai_client import AIResponse, OpenAIClient, OpenAIUnavailableError

logger = logging.getLogger(__name__)


# ── Suggestion generation ─────────────────────────────────────────────────────

_SUGGESTION_SYSTEM = """You are an expert interview assistant embedded inside a live recruiting platform.
Your task: analyse the interview transcript so far and suggest sharp, targeted follow-up questions for the interviewer.

RULES:
- Return ONLY valid JSON — no prose, no markdown fences.
- Each suggestion must have a clear rationale based on something the candidate actually said.
- Prefer open-ended questions that uncover depth, not yes/no questions.
- Suggestions should advance the conversation, not repeat ground already covered.
- Vary suggestion types as requested.

OUTPUT FORMAT:
{
  "suggestions": [
    {
      "suggestion_type": "<follow_up|clarification|skill_gap|deep_dive|closing>",
      "question_text": "<the actual question to ask>",
      "rationale": "<1-2 sentences: why this question is useful now>",
      "target_skills": ["<skill1>", "<skill2>"],
      "difficulty": "<easy|medium|hard>"
    }
  ]
}"""


def _build_suggestion_user_prompt(
    *,
    job_title: str,
    candidate_name: str,
    transcript_excerpt: str,
    required_skills: list[str],
    skills_covered: dict[str, bool],
    context_hint: str | None,
    suggestion_types: list[str] | None,
    count: int,
) -> str:
    uncovered = [s for s, covered in skills_covered.items() if not covered]
    covered = [s for s, c in skills_covered.items() if c]

    types_str = ", ".join(suggestion_types) if suggestion_types else "follow_up, clarification, skill_gap, deep_dive"
    uncovered_str = ", ".join(uncovered[:10]) if uncovered else "None — all skills appear covered"
    covered_str = ", ".join(covered[:10]) if covered else "None yet"

    hint_section = f"\nCONTEXT HINT FROM RECRUITER: {context_hint}" if context_hint else ""

    return f"""Generate {count} interview follow-up question suggestion(s) for this live interview.

JOB TITLE: {job_title}
CANDIDATE: {candidate_name}
REQUESTED SUGGESTION TYPES: {types_str}
{hint_section}

SKILLS ALREADY COVERED: {covered_str}
SKILLS NOT YET COVERED: {uncovered_str}

RECENT TRANSCRIPT (last ~500 words):
---
{transcript_excerpt[:3000] if transcript_excerpt else "(no transcript yet)"}
---

INSTRUCTIONS:
- Base suggestions on what was JUST said in the transcript.
- If skill_gap type is requested, probe uncovered skills directly.
- For deep_dive, pick the most technically interesting claim the candidate made.
- Closing suggestions should be used near the end: "What questions do you have for us?"
- Output exactly {count} suggestion(s)."""


@dataclass
class GeneratedSuggestion:
    suggestion_type: str
    question_text: str
    rationale: str | None = None
    target_skills: list[str] = field(default_factory=list)
    difficulty: str = "medium"


@dataclass
class SuggestionGenerationResult:
    suggestions: list[GeneratedSuggestion]
    prompt_tokens: int
    completion_tokens: int
    model: str
    fallback_used: bool = False


class CopilotSuggester:
    """Generates live interview suggestions and post-interview summaries."""

    def __init__(self, client: OpenAIClient | None = None) -> None:
        self._client = client or OpenAIClient()

    def generate_suggestions(
        self,
        *,
        job_title: str,
        candidate_name: str,
        transcript_excerpt: str,
        required_skills: list[str] | None = None,
        skills_covered: dict[str, bool] | None = None,
        context_hint: str | None = None,
        suggestion_types: list[str] | None = None,
        count: int = 3,
    ) -> SuggestionGenerationResult:
        """Generate follow-up question suggestions. Falls back gracefully if AI is unavailable."""

        user_prompt = _build_suggestion_user_prompt(
            job_title=job_title,
            candidate_name=candidate_name,
            transcript_excerpt=transcript_excerpt,
            required_skills=required_skills or [],
            skills_covered=skills_covered or {},
            context_hint=context_hint,
            suggestion_types=suggestion_types,
            count=count,
        )

        if not self._client.is_configured():
            logger.warning("copilot_suggester.openai_not_configured — using fallback suggestions")
            return self._fallback(count)

        try:
            response: AIResponse = self._client.chat_json(
                system=_SUGGESTION_SYSTEM,
                user=user_prompt,
                temperature=0.5,
                max_tokens=2000,
            )
            data = response.parse_json()
            suggestions = self._parse_suggestions(data)
            return SuggestionGenerationResult(
                suggestions=suggestions,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                model=response.model,
            )

        except OpenAIUnavailableError as exc:
            logger.warning("copilot_suggester.ai_unavailable: %s — using fallback", exc)
            return self._fallback(count, error=str(exc))

        except Exception as exc:
            logger.exception("copilot_suggester.unexpected_error: %s", exc)
            return self._fallback(count, error=str(exc))

    @staticmethod
    def _parse_suggestions(data: Any) -> list[GeneratedSuggestion]:
        raw_list = data.get("suggestions") or []
        valid_types = {"follow_up", "clarification", "skill_gap", "deep_dive", "closing"}
        valid_difficulties = {"easy", "medium", "hard"}
        result: list[GeneratedSuggestion] = []

        for item in raw_list[:8]:
            if not isinstance(item, dict):
                continue
            text = (item.get("question_text") or "").strip()
            if not text:
                continue
            s_type = item.get("suggestion_type", "follow_up")
            difficulty = item.get("difficulty", "medium")
            skills = item.get("target_skills")
            result.append(
                GeneratedSuggestion(
                    suggestion_type=s_type if s_type in valid_types else "follow_up",
                    question_text=text,
                    rationale=(item.get("rationale") or "").strip() or None,
                    target_skills=skills if isinstance(skills, list) else [],
                    difficulty=difficulty if difficulty in valid_difficulties else "medium",
                )
            )
        return result

    @staticmethod
    def _fallback(count: int, error: str | None = None) -> SuggestionGenerationResult:
        defaults = [
            GeneratedSuggestion(
                suggestion_type="follow_up",
                question_text="Can you walk me through a specific example of that?",
                rationale="Ask for a concrete story to validate the claim.",
                difficulty="easy",
            ),
            GeneratedSuggestion(
                suggestion_type="deep_dive",
                question_text="What was the most technically challenging part of that project, and how did you solve it?",
                rationale="Probe technical depth on what was just mentioned.",
                difficulty="medium",
            ),
            GeneratedSuggestion(
                suggestion_type="clarification",
                question_text="When you say you 'led' that initiative, what did your day-to-day involvement look like?",
                rationale="Clarify ownership and scope of contribution.",
                difficulty="easy",
            ),
            GeneratedSuggestion(
                suggestion_type="skill_gap",
                question_text="Tell me about a time you had to learn a new technology quickly under pressure.",
                rationale="Assess learning agility for uncovered skills.",
                difficulty="medium",
            ),
            GeneratedSuggestion(
                suggestion_type="closing",
                question_text="What questions do you have for us about the team or role?",
                rationale="Standard closing — gives candidate a chance to show engagement.",
                difficulty="easy",
            ),
        ]
        return SuggestionGenerationResult(
            suggestions=defaults[:count],
            prompt_tokens=0,
            completion_tokens=0,
            model="fallback",
            fallback_used=True,
        )


# ── Summary generation ────────────────────────────────────────────────────────

_SUMMARY_SYSTEM = """You are an expert technical recruiter generating a structured post-interview summary.
Analyse the full interview transcript and produce a concise, actionable debrief.

RULES:
- Return ONLY valid JSON — no prose, no markdown fences.
- Be specific: quote or paraphrase what the candidate actually said.
- Scores are 1–10.

OUTPUT FORMAT:
{
  "overall_impression": "<2-3 sentence executive summary>",
  "strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "concerns": ["<concern 1>", "<concern 2>"],
  "skills_demonstrated": {"<skill>": <score_1_to_10>, ...},
  "recommendation": "<strong_yes|yes|maybe|no>",
  "recommendation_rationale": "<2-3 sentences>",
  "suggested_next_steps": ["<step 1>", "<step 2>"]
}"""


def _build_summary_user_prompt(
    *,
    job_title: str,
    candidate_name: str,
    full_transcript: str,
    required_skills: list[str],
) -> str:
    skills_str = ", ".join(required_skills[:20]) if required_skills else "Not specified"
    return f"""Generate a post-interview summary for this interview.

JOB TITLE: {job_title}
CANDIDATE: {candidate_name}
REQUIRED SKILLS: {skills_str}

FULL TRANSCRIPT:
---
{full_transcript[:8000] if full_transcript else "(no transcript available)"}
---

Produce a structured debrief following the required JSON format."""


@dataclass
class InterviewSummaryResult:
    summary: dict
    prompt_tokens: int
    completion_tokens: int
    model: str
    fallback_used: bool = False


def generate_interview_summary(
    *,
    job_title: str,
    candidate_name: str,
    full_transcript: str,
    required_skills: list[str] | None = None,
    client: OpenAIClient | None = None,
) -> InterviewSummaryResult:
    """Generate a post-interview summary. Returns a fallback dict if AI is unavailable."""
    ai = client or OpenAIClient()

    user_prompt = _build_summary_user_prompt(
        job_title=job_title,
        candidate_name=candidate_name,
        full_transcript=full_transcript,
        required_skills=required_skills or [],
    )

    if not ai.is_configured():
        logger.warning("copilot_summary.openai_not_configured — using fallback summary")
        return _summary_fallback()

    try:
        response: AIResponse = ai.chat_json(
            system=_SUMMARY_SYSTEM,
            user=user_prompt,
            temperature=0.3,
            max_tokens=2048,
        )
        data = response.parse_json()
        return InterviewSummaryResult(
            summary=data,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            model=response.model,
        )

    except OpenAIUnavailableError as exc:
        logger.warning("copilot_summary.ai_unavailable: %s — using fallback", exc)
        return _summary_fallback()

    except Exception as exc:
        logger.exception("copilot_summary.unexpected_error: %s", exc)
        return _summary_fallback()


def _summary_fallback() -> InterviewSummaryResult:
    return InterviewSummaryResult(
        summary={
            "overall_impression": "Summary could not be generated — AI service unavailable.",
            "strengths": [],
            "concerns": [],
            "skills_demonstrated": {},
            "recommendation": "maybe",
            "recommendation_rationale": "Manual review required.",
            "suggested_next_steps": ["Review transcript manually and complete scorecard."],
        },
        prompt_tokens=0,
        completion_tokens=0,
        model="fallback",
        fallback_used=True,
    )
