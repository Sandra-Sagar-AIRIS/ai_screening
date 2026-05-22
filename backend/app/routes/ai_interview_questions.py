"""AI-003: Interview question generation endpoint.

POST /api/v1/ai/interview-questions
    Accepts job_title, job_description, required_skills.
    Returns 8-12 role-specific questions via OpenAI → Groq → static fallback.
    Hard timeout: 15 s per provider (enforced inside InterviewQuestionGenerator).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import AI_INTERVIEW_QUESTIONS_GENERATE
from app.schemas.ai_interview_questions import (
    GenerateInterviewQuestionsRequest,
    GenerateInterviewQuestionsResponse,
    InterviewQuestionSchema,
)
from app.services.ai.interview_question_generator import InterviewQuestionGenerator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ai"])

_generator = InterviewQuestionGenerator()


@router.post(
    "/ai/interview-questions",
    response_model=GenerateInterviewQuestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate role-specific interview questions (AI-003)",
)
def generate_interview_questions(
    payload: GenerateInterviewQuestionsRequest,
    _current_user=Depends(require_permission(AI_INTERVIEW_QUESTIONS_GENERATE)),
) -> GenerateInterviewQuestionsResponse:
    """Generate 8-12 interview questions tailored to the given job.

    Returns questions grouped by category (technical / behavioural / situational),
    each with an optional follow-up probe and ideal-answer traits.

    Errors:
    - 400 EMPTY_JOB_DESCRIPTION  — job_description is blank after stripping
    - 400 EMPTY_REQUIRED_SKILLS  — required_skills list is empty or all blank
    """
    # Extra semantic validation beyond Pydantic field constraints
    job_description = payload.job_description.strip()
    if not job_description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "EMPTY_JOB_DESCRIPTION"},
        )

    required_skills = [s.strip() for s in payload.required_skills if s.strip()]
    if not required_skills:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "EMPTY_REQUIRED_SKILLS"},
        )

    result = _generator.generate(
        job_title=payload.job_title.strip(),
        job_description=job_description,
        required_skills=required_skills,
    )

    logger.info(
        "ai003.generate_interview_questions provider=%s fallback=%s q_count=%d duration_ms=%d",
        result.provider_used,
        result.fallback_used,
        len(result.questions),
        result.duration_ms,
    )

    return GenerateInterviewQuestionsResponse(
        questions=[
            InterviewQuestionSchema(
                category=q.category,
                question_text=q.question_text,
                follow_up_probe=q.follow_up_probe,
                ideal_answer_traits=q.ideal_answer_traits,
            )
            for q in result.questions
        ],
        questions_by_category=result.questions_by_category,
        provider_used=result.provider_used,
        fallback_used=result.fallback_used,
        duration_ms=result.duration_ms,
    )
