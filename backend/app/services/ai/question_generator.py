"""AI question generation for screening sessions.

Generates 5–10 role-aware, difficulty-calibrated, categorised questions using
the job description, ATS gap analysis, candidate experience, and seniority level.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.services.ai.openai_client import AIResponse, OpenAIClient, OpenAIUnavailableError

logger = logging.getLogger(__name__)

# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an expert technical recruiter and screening architect for an enterprise ATS.
Your task: generate high-quality screening questions for a candidate interview.

RULES:
- Return ONLY valid JSON — no prose, no markdown fences.
- Generate between 5 and 10 questions total.
- Questions must be categorised, difficulty-aware, and role-specific.
- Expected signals describe what a strong answer looks like.
- Do NOT include answer text — only the question and evaluation guidance.

OUTPUT FORMAT:
{
  "questions": [
    {
      "category": "<one of: technical_depth|architecture|communication|behavioral|problem_solving|scalability|debugging|leadership>",
      "difficulty": "<easy|medium|hard>",
      "position": <integer starting at 1>,
      "question_text": "<the actual question to ask the candidate>",
      "expected_signals": {
        "key_concepts": ["<concept1>", "<concept2>"],
        "red_flags": ["<red flag to watch for>"],
        "ideal_depth": "<brief description of ideal answer depth>"
      }
    }
  ]
}"""


def _build_user_prompt(
    *,
    job_title: str,
    job_description: str,
    screening_type: str,
    candidate_experience_summary: str,
    candidate_skills: list[str],
    ats_gaps: list[str],
    seniority: str,
) -> str:
    skills_str = ", ".join(candidate_skills[:20]) if candidate_skills else "Not specified"
    gaps_str = ", ".join(ats_gaps[:10]) if ats_gaps else "None identified"

    return f"""Generate screening questions for the following context:

JOB TITLE: {job_title}
SCREENING TYPE: {screening_type}
SENIORITY LEVEL: {seniority}

JOB DESCRIPTION (excerpt):
{job_description[:2000] if job_description else "Not provided"}

CANDIDATE SKILLS: {skills_str}
IDENTIFIED SKILL GAPS (from ATS analysis): {gaps_str}
CANDIDATE EXPERIENCE SUMMARY: {candidate_experience_summary[:800] if candidate_experience_summary else "Not provided"}

INSTRUCTIONS:
- For screening_type=technical: 40% technical_depth, 20% problem_solving, 20% architecture, 10% debugging, 10% communication
- For screening_type=hr: 40% behavioral, 30% communication, 20% role_fit, 10% leadership
- For screening_type=behavioral: 50% behavioral, 25% leadership, 25% communication
- For screening_type=leadership: 40% leadership, 30% behavioral, 20% communication, 10% problem_solving
- For screening_type=communication: 60% communication, 20% behavioral, 20% role_fit
- For screening_type=role_fit: 40% behavioral, 30% role_fit concerns, 30% communication
- Target difficulty: HARD if senior/lead, MEDIUM for mid-level, EASY-MEDIUM for junior
- Probe ATS gaps directly in at least 2 questions
- Make questions open-ended and conversation-starting, not yes/no"""


# ── Dataclass output ──────────────────────────────────────────────────────────

@dataclass
class GeneratedQuestion:
    category: str
    difficulty: str
    position: int
    question_text: str
    expected_signals: dict | None = None


@dataclass
class QuestionGenerationResult:
    questions: list[GeneratedQuestion]
    prompt_tokens: int
    completion_tokens: int
    model: str
    fallback_used: bool = False


# ── Generator ────────────────────────────────────────────────────────────────

class QuestionGenerator:
    """Generates screening questions via OpenAI."""

    def __init__(self, client: OpenAIClient | None = None) -> None:
        self._client = client or OpenAIClient()

    def generate(
        self,
        *,
        job_title: str,
        job_description: str,
        screening_type: str,
        candidate_experience_summary: str = "",
        candidate_skills: list[str] | None = None,
        ats_gaps: list[str] | None = None,
        seniority: str = "mid-level",
    ) -> QuestionGenerationResult:
        """Generate questions. Returns a fallback set if AI is unavailable."""

        user_prompt = _build_user_prompt(
            job_title=job_title,
            job_description=job_description,
            screening_type=screening_type,
            candidate_experience_summary=candidate_experience_summary,
            candidate_skills=candidate_skills or [],
            ats_gaps=ats_gaps or [],
            seniority=seniority,
        )

        if not self._client.is_configured():
            logger.warning("question_generator.openai_not_configured — using fallback questions")
            return self._fallback(screening_type)

        try:
            response: AIResponse = self._client.chat_json(
                system=_SYSTEM_PROMPT,
                user=user_prompt,
                temperature=0.4,
                max_tokens=3000,
            )
            data = response.parse_json()
            questions = self._parse_questions(data)
            return QuestionGenerationResult(
                questions=questions,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                model=response.model,
            )

        except OpenAIUnavailableError as exc:
            logger.warning("question_generator.ai_unavailable: %s — using fallback", exc)
            return self._fallback(screening_type, error=str(exc))

        except Exception as exc:
            logger.exception("question_generator.unexpected_error: %s", exc)
            return self._fallback(screening_type, error=str(exc))

    @staticmethod
    def _parse_questions(data: Any) -> list[GeneratedQuestion]:
        raw_list = data.get("questions") or []
        questions: list[GeneratedQuestion] = []
        valid_categories = {
            "technical_depth", "architecture", "communication", "behavioral",
            "problem_solving", "scalability", "debugging", "leadership",
        }
        valid_difficulties = {"easy", "medium", "hard"}

        for i, q in enumerate(raw_list[:10]):
            if not isinstance(q, dict):
                continue
            text = q.get("question_text", "").strip()
            if not text:
                continue
            questions.append(
                GeneratedQuestion(
                    category=q.get("category", "behavioral") if q.get("category") in valid_categories else "behavioral",
                    difficulty=q.get("difficulty", "medium") if q.get("difficulty") in valid_difficulties else "medium",
                    position=q.get("position", i + 1),
                    question_text=text,
                    expected_signals=q.get("expected_signals") if isinstance(q.get("expected_signals"), dict) else None,
                )
            )
        return questions

    @staticmethod
    def _fallback(screening_type: str, error: str | None = None) -> QuestionGenerationResult:
        """Return generic fallback questions when AI is unavailable."""
        base_questions = [
            GeneratedQuestion(
                category="behavioral",
                difficulty="medium",
                position=1,
                question_text="Tell me about a challenging project you worked on recently. What was your role and what did you learn?",
                expected_signals={"key_concepts": ["ownership", "problem-solving", "reflection"]},
            ),
            GeneratedQuestion(
                category="communication",
                difficulty="easy",
                position=2,
                question_text="How do you communicate technical concepts to non-technical stakeholders?",
                expected_signals={"key_concepts": ["clarity", "empathy", "examples"]},
            ),
            GeneratedQuestion(
                category="problem_solving",
                difficulty="medium",
                position=3,
                question_text="Describe your process when you encounter a bug you've never seen before.",
                expected_signals={"key_concepts": ["systematic approach", "debugging methodology"]},
            ),
            GeneratedQuestion(
                category="behavioral",
                difficulty="medium",
                position=4,
                question_text="How do you manage competing priorities when multiple deadlines approach simultaneously?",
                expected_signals={"key_concepts": ["prioritisation", "communication", "delivery"]},
            ),
            GeneratedQuestion(
                category="communication",
                difficulty="medium",
                position=5,
                question_text="What questions do you have about this role and the team?",
                expected_signals={"key_concepts": ["curiosity", "engagement", "preparation"]},
            ),
        ]
        return QuestionGenerationResult(
            questions=base_questions,
            prompt_tokens=0,
            completion_tokens=0,
            model="fallback",
            fallback_used=True,
        )
