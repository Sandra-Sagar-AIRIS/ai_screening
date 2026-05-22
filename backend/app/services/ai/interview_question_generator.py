"""AI-003: Interview question generator.

Generates 8-12 role-specific interview questions (technical / behavioural / situational)
from a job description and required skills list.

Provider chain
--------------
1. OpenAI (primary)  — uses OPENAI_API_KEY + OPENAI_API_BASE
2. Groq / LLaMA      — fallback when OpenAI is unavailable or times out
3. Static fallback   — if both AI providers fail

Hard timeout of 15 seconds per provider call (spec requirement).
Fallback is attempted within the same 15 s window if primary fails fast.
"""
from __future__ import annotations

import json
import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT_S = 15.0  # AI-003 requirement: timeout after 15 seconds

# ── Prompt templates ──────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a senior technical interviewer and talent specialist.
Your task: generate high-quality, role-specific interview questions for a job opening.

RULES:
- Return ONLY valid JSON — no prose, no markdown code fences.
- Generate between 8 and 12 questions total.
- Question mix: ~4 technical, ~4 behavioural, ~2-4 situational.
- Every question MUST reference the job role or a required skill directly.
- Avoid generic, skill-agnostic questions.
- follow_up_probe is optional but encouraged where useful.
- ideal_answer_traits: 3-5 concise, role-relevant traits per question.

OUTPUT FORMAT (strict JSON):
{
  "questions": [
    {
      "category": "technical",
      "question_text": "...",
      "follow_up_probe": "...",
      "ideal_answer_traits": ["trait1", "trait2", "trait3"]
    }
  ]
}

Valid categories: technical, behavioural, situational"""


def _build_user_prompt(
    *,
    job_title: str,
    job_description: str,
    required_skills: list[str],
) -> str:
    skills_str = ", ".join(required_skills[:20])
    return f"""Generate interview questions for the following role:

JOB TITLE: {job_title}
REQUIRED SKILLS: {skills_str}

JOB DESCRIPTION:
{job_description[:3000]}

INSTRUCTIONS:
- Technical questions must probe depth of knowledge in the required skills listed above.
- Behavioural questions should surface relevant work experiences and collaboration patterns.
- Situational questions should present realistic on-the-job challenges for this role.
- Each question_text must be specific enough that a generic candidate could NOT copy-paste a template answer.
- ideal_answer_traits should tell the interviewer what "good" looks like for THIS role."""


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class InterviewQuestion:
    category: str
    question_text: str
    follow_up_probe: str | None
    ideal_answer_traits: list[str]


@dataclass
class QuestionGenerationResult:
    questions: list[InterviewQuestion]
    questions_by_category: dict[str, int]
    provider_used: str
    fallback_used: bool = False
    duration_ms: int = 0


# ── Private helpers ───────────────────────────────────────────────────────────

def _parse_questions(raw: Any) -> list[InterviewQuestion]:
    """Parse and validate the AI JSON payload into typed question objects."""
    valid_categories = {"technical", "behavioural", "situational"}
    raw_list = raw.get("questions") or [] if isinstance(raw, dict) else []
    questions: list[InterviewQuestion] = []

    for q in raw_list[:12]:
        if not isinstance(q, dict):
            continue
        text = (q.get("question_text") or "").strip()
        if not text:
            continue
        cat = (q.get("category") or "").lower().strip()
        if cat not in valid_categories:
            cat = "behavioural"
        traits = q.get("ideal_answer_traits") or []
        if not isinstance(traits, list):
            traits = []
        traits = [str(t).strip() for t in traits if str(t).strip()][:5]
        if not traits:
            traits = ["Role-specific knowledge", "Clear communication", "Practical experience"]
        probe = (q.get("follow_up_probe") or "").strip() or None
        questions.append(
            InterviewQuestion(
                category=cat,
                question_text=text,
                follow_up_probe=probe,
                ideal_answer_traits=traits,
            )
        )
    return questions


def _count_by_category(questions: list[InterviewQuestion]) -> dict[str, int]:
    counts: dict[str, int] = {"technical": 0, "behavioural": 0, "situational": 0}
    for q in questions:
        if q.category in counts:
            counts[q.category] += 1
    return counts


def _extract_json(content: str) -> Any:
    """Strip markdown fences and parse JSON from an AI response."""
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]+?)```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def _static_fallback(
    job_title: str,
    required_skills: list[str],
) -> QuestionGenerationResult:
    """Last-resort fallback — samples from a large pool so questions vary each call.

    Pool: 8 technical (parameterised on primary skill), 8 behavioural, 6 situational
    → 22 total. Random sample of 10 (4 tech / 4 beh / 2 sit) is returned each call.
    """
    s = required_skills[0] if required_skills else "the core technology"
    s2 = required_skills[1] if len(required_skills) > 1 else s

    technical_pool: list[InterviewQuestion] = [
        InterviewQuestion(
            category="technical",
            question_text=f"Walk me through how you would design a production-ready system using {s}. What are the key architectural decisions you'd make?",
            follow_up_probe="How would you handle scaling or failure scenarios?",
            ideal_answer_traits=["System design clarity", f"Hands-on {s} experience", "Awareness of trade-offs", "Production mindset"],
        ),
        InterviewQuestion(
            category="technical",
            question_text=f"What are the most common pitfalls when working with {s}, and how have you avoided them?",
            follow_up_probe="Can you give a specific example from a recent project?",
            ideal_answer_traits=["Practical experience", "Attention to edge cases", "Self-awareness", "Mentorship potential"],
        ),
        InterviewQuestion(
            category="technical",
            question_text=f"Describe how you would debug a performance issue in a {s}-based service in production.",
            follow_up_probe="Which tools or metrics do you reach for first?",
            ideal_answer_traits=["Systematic debugging", "Tooling knowledge", "Root-cause focus", "Calm under pressure"],
        ),
        InterviewQuestion(
            category="technical",
            question_text=f"How do you stay current with changes and best practices in {s}?",
            follow_up_probe=None,
            ideal_answer_traits=["Continuous learning", "Community involvement", "Applies learning to work", "Shares knowledge"],
        ),
        InterviewQuestion(
            category="technical",
            question_text=f"Explain how you would approach testing a complex {s} component — what levels of testing would you apply?",
            follow_up_probe="How do you decide when you have enough test coverage?",
            ideal_answer_traits=["Testing strategy", "Unit vs integration vs e2e", "Coverage pragmatism", "CI/CD mindset"],
        ),
        InterviewQuestion(
            category="technical",
            question_text=f"How would you approach a migration of a legacy system to {s}? What risks would you flag upfront?",
            follow_up_probe="How do you keep the old system running during the cutover?",
            ideal_answer_traits=["Migration planning", "Risk identification", "Backward compatibility", "Incremental delivery"],
        ),
        InterviewQuestion(
            category="technical",
            question_text=f"Describe a time you had to optimise a slow or expensive operation in {s}. What was your process?",
            follow_up_probe="How did you measure the improvement?",
            ideal_answer_traits=["Profiling skills", "Data-driven approach", "Impact measurement", f"{s} internals knowledge"],
        ),
        InterviewQuestion(
            category="technical",
            question_text=f"What security considerations are specific to working with {s2} in a production environment?",
            follow_up_probe="Have you encountered a security issue in this area? How was it handled?",
            ideal_answer_traits=["Security awareness", "Threat modelling", "Defensive coding", "Incident experience"],
        ),
    ]

    behavioural_pool: list[InterviewQuestion] = [
        InterviewQuestion(
            category="behavioural",
            question_text=f"Tell me about a time you delivered a complex {job_title} project under tight deadlines. What did you do differently?",
            follow_up_probe="What would you change if you could do it again?",
            ideal_answer_traits=["Ownership", "Prioritisation", "Delivery under pressure", "Retrospective mindset"],
        ),
        InterviewQuestion(
            category="behavioural",
            question_text="Describe a situation where you had to push back on a technical decision you disagreed with. How did you handle it?",
            follow_up_probe="What was the outcome and how did it affect the team?",
            ideal_answer_traits=["Assertiveness with respect", "Evidence-based arguments", "Team orientation", "Conflict resolution"],
        ),
        InterviewQuestion(
            category="behavioural",
            question_text="Give an example of a time you mentored or brought a less experienced colleague up to speed on a technical topic.",
            follow_up_probe="How did you measure whether the mentoring was effective?",
            ideal_answer_traits=["Teaching ability", "Patience", "Structured communication", "Team investment"],
        ),
        InterviewQuestion(
            category="behavioural",
            question_text="Tell me about a project that failed or didn't go as planned. What did you learn from it?",
            follow_up_probe="Did that change how you approach similar work now?",
            ideal_answer_traits=["Honesty and accountability", "Learning from failure", "Growth mindset", "Process improvement"],
        ),
        InterviewQuestion(
            category="behavioural",
            question_text="Describe a time when you had to quickly get up to speed on an unfamiliar technology or codebase. How did you approach it?",
            follow_up_probe="What would you do differently the next time?",
            ideal_answer_traits=["Learning agility", "Structured approach", "Resourcefulness", "Asking good questions"],
        ),
        InterviewQuestion(
            category="behavioural",
            question_text="Tell me about a time you improved a development process or workflow for your team.",
            follow_up_probe="How did you get buy-in from the rest of the team?",
            ideal_answer_traits=["Process thinking", "Influence without authority", "Measurable impact", "Team-first mindset"],
        ),
        InterviewQuestion(
            category="behavioural",
            question_text="Describe a situation where you received critical feedback on your work. How did you respond?",
            follow_up_probe="Did you change your approach as a result?",
            ideal_answer_traits=["Receptiveness to feedback", "Self-reflection", "Adaptability", "Professionalism"],
        ),
        InterviewQuestion(
            category="behavioural",
            question_text="Tell me about a time you had to collaborate with a non-technical stakeholder to deliver something complex. What challenges came up?",
            follow_up_probe="How do you adapt your communication style for different audiences?",
            ideal_answer_traits=["Cross-functional collaboration", "Plain-language explanations", "Stakeholder management", "Empathy"],
        ),
    ]

    situational_pool: list[InterviewQuestion] = [
        InterviewQuestion(
            category="situational",
            question_text=f"You join as a {job_title} and discover that a critical production system has undocumented technical debt. How would you approach it?",
            follow_up_probe="How do you balance fixing it against feature delivery pressure?",
            ideal_answer_traits=["Pragmatism", "Stakeholder communication", "Risk assessment", "Incremental improvement"],
        ),
        InterviewQuestion(
            category="situational",
            question_text="Your team is mid-sprint and a high-priority production incident occurs. How do you decide whether to stop current work and respond?",
            follow_up_probe=None,
            ideal_answer_traits=["Incident triage skills", "Clear decision criteria", "Communication", "Team coordination"],
        ),
        InterviewQuestion(
            category="situational",
            question_text=f"You are asked to estimate how long a feature will take, but the requirements are still vague. How do you handle it?",
            follow_up_probe="How do you communicate uncertainty in your estimate to the team?",
            ideal_answer_traits=["Estimation under uncertainty", "Requirement clarification", "Range-based thinking", "Honest communication"],
        ),
        InterviewQuestion(
            category="situational",
            question_text="Two senior engineers on your team have a strong disagreement about the right technical approach. You're the newest member. What do you do?",
            follow_up_probe="Would your answer change if you were the tech lead?",
            ideal_answer_traits=["Navigating conflict", "Constructive input", "Diplomatic courage", "Team cohesion"],
        ),
        InterviewQuestion(
            category="situational",
            question_text=f"You discover a security vulnerability in the codebase the day before a major release. How do you handle it?",
            follow_up_probe="How do you communicate this to non-technical stakeholders?",
            ideal_answer_traits=["Security judgement", "Risk vs release trade-off", "Clear escalation", "Calm decision-making"],
        ),
        InterviewQuestion(
            category="situational",
            question_text="You're assigned a task with no clear owner, unclear requirements, and a tight deadline. Walk me through how you'd approach it.",
            follow_up_probe="What do you do if you can't get clarification in time?",
            ideal_answer_traits=["Autonomy", "Scope-setting", "Proactive communication", "Bias for action"],
        ),
    ]

    # Sample a varied set each call: 4 technical + 4 behavioural + 2 situational
    questions = (
        random.sample(technical_pool, min(4, len(technical_pool)))
        + random.sample(behavioural_pool, min(4, len(behavioural_pool)))
        + random.sample(situational_pool, min(2, len(situational_pool)))
    )

    return QuestionGenerationResult(
        questions=questions,
        questions_by_category=_count_by_category(questions),
        provider_used="static-fallback",
        fallback_used=True,
    )


# ── Generator ─────────────────────────────────────────────────────────────────

class InterviewQuestionGenerator:
    """AI-003: Generates tailored interview questions using OpenAI → Groq fallback chain.

    Enforces a 15-second hard timeout per provider call.
    """

    def generate(
        self,
        *,
        job_title: str,
        job_description: str,
        required_skills: list[str],
    ) -> QuestionGenerationResult:
        """Generate 8–12 interview questions.

        Returns a QuestionGenerationResult regardless of provider success.
        Callers should check `result.fallback_used` and `result.provider_used`
        for observability.
        """
        t0 = time.monotonic()
        settings = get_settings()
        system_prompt = _SYSTEM_PROMPT
        user_prompt = _build_user_prompt(
            job_title=job_title,
            job_description=job_description,
            required_skills=required_skills,
        )

        # ── 1. Try OpenAI (primary) ────────────────────────────────────────
        openai_key = (settings.openai_api_key or "").strip()
        if openai_key:
            try:
                result = self._call_openai(
                    api_key=openai_key,
                    api_base=(settings.openai_api_base or "https://api.openai.com/v1").rstrip("/"),
                    model=settings.openai_screening_model or "gpt-4.1-mini",
                    system=system_prompt,
                    user=user_prompt,
                )
                result.duration_ms = int((time.monotonic() - t0) * 1000)
                logger.info(
                    "ai003.interview_questions.openai_success provider=%s duration_ms=%d fallback=%s",
                    result.provider_used, result.duration_ms, result.fallback_used,
                )
                return result
            except TimeoutError:
                logger.warning(
                    "ai003.interview_questions.openai_timeout duration_ms=%d — trying Groq fallback",
                    int((time.monotonic() - t0) * 1000),
                )
            except Exception as exc:
                logger.warning(
                    "ai003.interview_questions.openai_error: %s — trying Groq fallback", exc
                )

        # ── 2. Try Groq (fallback) ─────────────────────────────────────────
        groq_key = (settings.groq_api_key or "").strip()
        if groq_key:
            try:
                result = self._call_groq(
                    api_key=groq_key,
                    system=system_prompt,
                    user=user_prompt,
                )
                result.fallback_used = not bool(openai_key)  # only flag as fallback if openai was tried first
                result.fallback_used = True if openai_key else result.fallback_used
                result.duration_ms = int((time.monotonic() - t0) * 1000)
                logger.info(
                    "ai003.interview_questions.groq_success provider=%s duration_ms=%d",
                    result.provider_used, result.duration_ms,
                )
                return result
            except TimeoutError:
                logger.warning(
                    "ai003.interview_questions.groq_timeout duration_ms=%d",
                    int((time.monotonic() - t0) * 1000),
                )
            except Exception as exc:
                logger.warning("ai003.interview_questions.groq_error: %s", exc)

        # ── 3. Static fallback ─────────────────────────────────────────────
        logger.warning(
            "ai003.interview_questions.static_fallback no_ai_keys_configured=%s",
            not openai_key and not groq_key,
        )
        result = _static_fallback(job_title=job_title, required_skills=required_skills)
        result.duration_ms = int((time.monotonic() - t0) * 1000)
        return result

    # ── Provider calls ─────────────────────────────────────────────────────

    def _call_openai(
        self,
        *,
        api_key: str,
        api_base: str,
        model: str,
        system: str,
        user: str,
    ) -> QuestionGenerationResult:
        payload = {
            "model": model,
            "temperature": 0.8,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.post(f"{api_base}/chat/completions", headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise TimeoutError("OpenAI request timed out") from exc

        duration_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code >= 400:
            raise RuntimeError(f"OpenAI HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI returned empty choices")
        content = (choices[0].get("message") or {}).get("content") or ""
        if not content.strip():
            raise RuntimeError("OpenAI returned empty content")

        raw = _extract_json(content)
        questions = _parse_questions(raw)

        if len(questions) < 8:
            raise RuntimeError(f"OpenAI returned only {len(questions)} questions (need ≥8)")

        logger.info(
            "ai003.openai duration_ms=%d prompt_tokens=%d completion_tokens=%d model=%s",
            duration_ms,
            (data.get("usage") or {}).get("prompt_tokens", 0),
            (data.get("usage") or {}).get("completion_tokens", 0),
            data.get("model", model),
        )
        return QuestionGenerationResult(
            questions=questions,
            questions_by_category=_count_by_category(questions),
            provider_used=f"openai/{data.get('model', model)}",
            fallback_used=False,
            duration_ms=duration_ms,
        )

    def _call_groq(
        self,
        *,
        api_key: str,
        system: str,
        user: str,
    ) -> QuestionGenerationResult:
        settings = get_settings()
        api_base = (settings.groq_ats_api_base or "https://api.groq.com/openai/v1").rstrip("/")
        model = settings.groq_ats_model or "llama-3.3-70b-versatile"

        payload = {
            "model": model,
            "temperature": 0.7,
            "max_tokens": 4096,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        t0 = time.monotonic()
        try:
            with httpx.Client(timeout=_TIMEOUT_S) as client:
                resp = client.post(f"{api_base}/chat/completions", headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise TimeoutError("Groq request timed out") from exc

        duration_ms = int((time.monotonic() - t0) * 1000)

        if resp.status_code >= 400:
            raise RuntimeError(f"Groq HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("Groq returned empty choices")
        content = (choices[0].get("message") or {}).get("content") or ""
        if not content.strip():
            raise RuntimeError("Groq returned empty content")

        raw = _extract_json(content)
        questions = _parse_questions(raw)

        if len(questions) < 8:
            raise RuntimeError(f"Groq returned only {len(questions)} questions (need ≥8)")

        logger.info(
            "ai003.groq duration_ms=%d model=%s q_count=%d",
            duration_ms, model, len(questions),
        )
        return QuestionGenerationResult(
            questions=questions,
            questions_by_category=_count_by_category(questions),
            provider_used=f"groq/{model}",
            fallback_used=True,
            duration_ms=duration_ms,
        )
