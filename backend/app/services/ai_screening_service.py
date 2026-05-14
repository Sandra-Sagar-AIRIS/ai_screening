"""AI Screening Service — orchestrates the full screening lifecycle.

Workflow:
  1. create_screening()  → creates AIScreening row with status=pending
  2. generate_questions() → calls QuestionGenerator, persists questions, status=questions_ready
  3. upsert_answer()     → recruiter enters/updates an answer for a question
  4. run_evaluation()    → evaluates each answered question, computes scores, status=completed
  5. get_detail()        → returns full screening + Q+A+evaluations for recruiter review
  6. record_recruiter_decision() → stores recruiter override decision

generate_questions() and run_evaluation() are designed to be called from
FastAPI BackgroundTasks so they never block HTTP responses.

All errors are caught and persisted as status=failed so recruiters can retry.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_screening import (
    AIScreening,
    AIScreeningAnswer,
    AIScreeningEvaluation,
    AIScreeningQuestion,
)
from app.models.candidate import Candidate
from app.models.job import Job
from app.schemas.ai_screening import (
    AIScreeningCreate,
    AIScreeningDetailResponse,
    AIScreeningListItem,
    AIScreeningQuestionResponse,
    AIScreeningAnswerResponse,
    AIScreeningEvaluationResponse,
    AIScreeningResponse,
    AnswerUpsert,
)
from app.schemas.auth import CurrentUser
from app.services.ai.answer_evaluator import AnswerEvaluator
from app.services.ai.question_generator import QuestionGenerator
from app.services.ai.recommendation_engine import compute_scores_and_recommendation
from app.services.ai.recruiter_summary import RecruiterSummaryGenerator

logger = logging.getLogger(__name__)


class AIScreeningService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._question_gen = QuestionGenerator()
        self._evaluator = AnswerEvaluator()
        self._summarizer = RecruiterSummaryGenerator()

    # ── Create ────────────────────────────────────────────────────────────────

    def create_screening(
        self,
        org_id: UUID,
        current_user: CurrentUser,
        payload: AIScreeningCreate,
    ) -> AIScreening:
        screening = AIScreening(
            organization_id=org_id,
            candidate_id=payload.candidate_id,
            job_id=payload.job_id,
            created_by=UUID(current_user.user_id),
            status="pending",
            screening_type=payload.screening_type.value,
        )
        self.db.add(screening)
        self.db.commit()
        self.db.refresh(screening)
        return screening

    # ── List ─────────────────────────────────────────────────────────────────

    def list_screenings(
        self,
        org_id: UUID,
        *,
        candidate_id: UUID | None = None,
        job_id: UUID | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AIScreeningListItem]:
        stmt = (
            select(AIScreening)
            .where(AIScreening.organization_id == org_id)
            .order_by(AIScreening.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if candidate_id:
            stmt = stmt.where(AIScreening.candidate_id == candidate_id)
        if job_id:
            stmt = stmt.where(AIScreening.job_id == job_id)
        if status:
            stmt = stmt.where(AIScreening.status == status)

        rows = list(self.db.scalars(stmt))
        items: list[AIScreeningListItem] = []
        for row in rows:
            candidate = self.db.get(Candidate, row.candidate_id)
            job = self.db.get(Job, row.job_id) if row.job_id else None
            items.append(
                AIScreeningListItem(
                    id=row.id,
                    candidate_id=row.candidate_id,
                    job_id=row.job_id,
                    status=row.status,
                    screening_type=row.screening_type,
                    overall_score=float(row.overall_score) if row.overall_score is not None else None,
                    recommendation=row.recommendation,
                    recruiter_decision=row.recruiter_decision,
                    created_at=row.created_at,
                    completed_at=row.completed_at,
                    candidate_name=f"{candidate.first_name} {candidate.last_name}" if candidate else None,
                    candidate_email=candidate.email if candidate else None,
                    job_title=job.title if job else None,
                )
            )
        return items

    # ── Get detail ────────────────────────────────────────────────────────────

    def get_screening(self, org_id: UUID, screening_id: UUID) -> AIScreening:
        row = self.db.scalar(
            select(AIScreening).where(
                AIScreening.id == screening_id,
                AIScreening.organization_id == org_id,
            )
        )
        if row is None:
            from fastapi import HTTPException, status as http_status
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Screening not found")
        return row

    def get_screening_detail(
        self, org_id: UUID, screening_id: UUID
    ) -> AIScreeningDetailResponse:
        screening = self.get_screening(org_id, screening_id)

        questions = list(
            self.db.scalars(
                select(AIScreeningQuestion)
                .where(AIScreeningQuestion.screening_id == screening_id)
                .order_by(AIScreeningQuestion.position)
            )
        )
        answers = list(
            self.db.scalars(
                select(AIScreeningAnswer)
                .where(AIScreeningAnswer.screening_id == screening_id)
            )
        )
        evaluations = list(
            self.db.scalars(
                select(AIScreeningEvaluation)
                .where(AIScreeningEvaluation.screening_id == screening_id)
            )
        )

        candidate = self.db.get(Candidate, screening.candidate_id)
        job = self.db.get(Job, screening.job_id) if screening.job_id else None

        # Fetch ATS score if available
        ats_score = None
        ats_recommendation = None
        try:
            from app.models.candidate_job_match import CandidateJobMatch
            if screening.job_id:
                match = self.db.scalar(
                    select(CandidateJobMatch).where(
                        CandidateJobMatch.candidate_id == screening.candidate_id,
                        CandidateJobMatch.job_id == screening.job_id,
                    )
                )
                if match:
                    ats_score = float(match.final_score) if match.final_score is not None else None
                    ats_recommendation = match.recommendation
        except Exception:
            pass  # ATS data is supplemental — never break the screening view

        return AIScreeningDetailResponse(
            **AIScreeningResponse.model_validate(screening).model_dump(),
            questions=[AIScreeningQuestionResponse.model_validate(q) for q in questions],
            answers=[AIScreeningAnswerResponse.model_validate(a) for a in answers],
            evaluations=[AIScreeningEvaluationResponse.model_validate(e) for e in evaluations],
            candidate_name=f"{candidate.first_name} {candidate.last_name}" if candidate else None,
            candidate_email=candidate.email if candidate else None,
            job_title=job.title if job else None,
            ats_score=ats_score,
            ats_recommendation=ats_recommendation,
        )

    # ── Generate questions (designed for BackgroundTasks) ────────────────────

    def generate_questions(self, org_id: UUID, screening_id: UUID) -> None:
        """Generate AI questions for a screening. Safe to call from background."""
        try:
            screening = self.get_screening(org_id, screening_id)
            screening.status = "generating_questions"
            self.db.add(screening)
            self.db.commit()

            # Load context
            candidate = self.db.get(Candidate, screening.candidate_id)
            job = self.db.get(Job, screening.job_id) if screening.job_id else None

            # Resolve seniority from candidate data
            seniority = _infer_seniority(candidate)
            candidate_skills: list[str] = []
            ats_gaps: list[str] = []

            if candidate:
                parsed = getattr(candidate, "parsed_resume_data", None) or {}
                candidate_skills = (
                    (parsed.get("skills") or []) + (parsed.get("inferred_skills") or [])
                )[:20]

            # Pull ATS skill gaps if available
            if job and candidate:
                try:
                    from app.models.candidate_job_match import CandidateJobMatch
                    match = self.db.scalar(
                        select(CandidateJobMatch).where(
                            CandidateJobMatch.candidate_id == candidate.id,
                            CandidateJobMatch.job_id == job.id,
                        )
                    )
                    if match and match.score_breakdown:
                        breakdown = match.score_breakdown or {}
                        ats_gaps = breakdown.get("missing_skills", [])[:10]
                except Exception:
                    pass

            result = self._question_gen.generate(
                job_title=job.title if job else "Unknown Role",
                job_description=job.description if job else "",
                screening_type=screening.screening_type,
                candidate_experience_summary=getattr(candidate, "experience_summary", "") or "",
                candidate_skills=candidate_skills,
                ats_gaps=ats_gaps,
                seniority=seniority,
            )

            # Persist questions
            for q in result.questions:
                self.db.add(
                    AIScreeningQuestion(
                        screening_id=screening_id,
                        category=q.category,
                        difficulty=q.difficulty,
                        position=q.position,
                        question_text=q.question_text,
                        expected_signals=q.expected_signals,
                        generated_by_ai=not result.fallback_used,
                    )
                )

            screening.status = "questions_ready"
            screening.ai_model = result.model
            screening.prompt_tokens_used = (screening.prompt_tokens_used or 0) + result.prompt_tokens
            screening.completion_tokens_used = (screening.completion_tokens_used or 0) + result.completion_tokens
            screening.generation_context = {
                "seniority": seniority,
                "skills_used": candidate_skills[:10],
                "ats_gaps_used": ats_gaps[:5],
                "fallback_used": result.fallback_used,
            }
            self.db.add(screening)
            self.db.commit()
            logger.info("screening.questions_generated screening_id=%s count=%d", screening_id, len(result.questions))

        except Exception as exc:
            logger.exception("screening.generate_questions.failed screening_id=%s: %s", screening_id, exc)
            try:
                screening = self.db.get(AIScreening, screening_id)
                if screening:
                    screening.status = "failed"
                    self.db.add(screening)
                    self.db.commit()
            except Exception:
                pass

    # ── Answers ───────────────────────────────────────────────────────────────

    def upsert_answer(
        self,
        org_id: UUID,
        screening_id: UUID,
        question_id: UUID,
        payload: AnswerUpsert,
    ) -> AIScreeningAnswer:
        """Create or replace the answer for a question."""
        self.get_screening(org_id, screening_id)  # ownership check

        existing = self.db.scalar(
            select(AIScreeningAnswer).where(
                AIScreeningAnswer.screening_id == screening_id,
                AIScreeningAnswer.question_id == question_id,
            )
        )
        if existing:
            existing.answer_text = payload.answer_text
            existing.source_type = payload.source_type.value
            self.db.add(existing)
            self.db.commit()
            self.db.refresh(existing)
            return existing

        answer = AIScreeningAnswer(
            screening_id=screening_id,
            question_id=question_id,
            answer_text=payload.answer_text,
            recruiter_entered=True,
            source_type=payload.source_type.value,
        )
        self.db.add(answer)
        self.db.commit()
        self.db.refresh(answer)
        return answer

    # ── Evaluate (designed for BackgroundTasks) ───────────────────────────────

    def run_evaluation(self, org_id: UUID, screening_id: UUID) -> None:
        """Evaluate all answered questions. Safe to call from background."""
        try:
            screening = self.get_screening(org_id, screening_id)
            screening.status = "evaluating"
            self.db.add(screening)
            self.db.commit()

            job = self.db.get(Job, screening.job_id) if screening.job_id else None
            candidate = self.db.get(Candidate, screening.candidate_id)
            job_title = job.title if job else "Unknown Role"

            questions = list(
                self.db.scalars(
                    select(AIScreeningQuestion)
                    .where(AIScreeningQuestion.screening_id == screening_id)
                    .order_by(AIScreeningQuestion.position)
                )
            )
            answers_by_qid: dict[UUID, AIScreeningAnswer] = {}
            for ans in self.db.scalars(
                select(AIScreeningAnswer).where(AIScreeningAnswer.screening_id == screening_id)
            ):
                answers_by_qid[ans.question_id] = ans

            total_prompt_tokens = 0
            total_completion_tokens = 0
            eval_dicts: list[dict] = []
            qa_for_summary: list[dict] = []

            for question in questions:
                answer = answers_by_qid.get(question.id)
                if not answer:
                    continue

                # Remove stale evaluation if exists
                old_eval = self.db.scalar(
                    select(AIScreeningEvaluation).where(
                        AIScreeningEvaluation.screening_id == screening_id,
                        AIScreeningEvaluation.question_id == question.id,
                    )
                )
                if old_eval:
                    self.db.delete(old_eval)
                    self.db.flush()

                result = self._evaluator.evaluate(
                    job_title=job_title,
                    question_text=question.question_text,
                    question_category=question.category,
                    expected_signals=question.expected_signals,
                    answer_text=answer.answer_text,
                )

                eval_row = AIScreeningEvaluation(
                    screening_id=screening_id,
                    question_id=question.id,
                    ai_score=result.ai_score,
                    communication_rating=result.communication_rating,
                    technical_rating=result.technical_rating,
                    strengths=result.strengths,
                    concerns=result.concerns,
                    reasoning=result.reasoning,
                    follow_up_suggestion=result.follow_up_suggestion,
                    confidence=result.confidence,
                )
                self.db.add(eval_row)
                total_prompt_tokens += result.prompt_tokens
                total_completion_tokens += result.completion_tokens

                eval_dicts.append({
                    "ai_score": result.ai_score,
                    "communication_rating": result.communication_rating,
                    "technical_rating": result.technical_rating,
                    "confidence": result.confidence,
                })
                qa_for_summary.append({
                    "question": question.question_text,
                    "category": question.category,
                    "ai_score": result.ai_score,
                    "strengths": result.strengths,
                    "concerns": result.concerns,
                })

            self.db.flush()

            # Compute aggregate scores
            scores = compute_scores_and_recommendation(
                evaluations=eval_dicts,
                screening_type=screening.screening_type,
            )

            # Generate recruiter summary
            candidate_name = (
                f"{candidate.first_name} {candidate.last_name}" if candidate else "Candidate"
            )
            summary_result = self._summarizer.generate(
                candidate_name=candidate_name,
                job_title=job_title,
                screening_type=screening.screening_type,
                questions_and_evaluations=qa_for_summary,
                aggregate_scores={
                    "overall": scores.overall_score,
                    "technical": scores.technical_score,
                    "communication": scores.communication_score,
                    "confidence": scores.confidence_score,
                },
            )

            total_prompt_tokens += summary_result.prompt_tokens
            total_completion_tokens += summary_result.completion_tokens

            # Build the AI summary text
            ai_summary_parts = [summary_result.overall_assessment]
            if summary_result.key_strengths:
                ai_summary_parts.append("Key strengths: " + "; ".join(summary_result.key_strengths))
            if summary_result.key_concerns:
                ai_summary_parts.append("Concerns: " + "; ".join(summary_result.key_concerns))
            if summary_result.follow_up_focus_areas:
                ai_summary_parts.append(
                    "Suggested interview focus: " + "; ".join(summary_result.follow_up_focus_areas)
                )

            # Persist aggregate results
            screening.status = "completed"
            screening.overall_score = scores.overall_score
            screening.communication_score = scores.communication_score
            screening.technical_score = scores.technical_score
            screening.confidence_score = scores.confidence_score
            screening.recommendation = scores.recommendation
            screening.ai_summary = "\n\n".join(ai_summary_parts)
            screening.completed_at = datetime.now(UTC)
            screening.prompt_tokens_used = (screening.prompt_tokens_used or 0) + total_prompt_tokens
            screening.completion_tokens_used = (screening.completion_tokens_used or 0) + total_completion_tokens
            self.db.add(screening)
            self.db.commit()

            logger.info(
                "screening.evaluation_completed screening_id=%s score=%.1f recommendation=%s",
                screening_id, scores.overall_score, scores.recommendation,
            )

        except Exception as exc:
            logger.exception("screening.run_evaluation.failed screening_id=%s: %s", screening_id, exc)
            try:
                s = self.db.get(AIScreening, screening_id)
                if s:
                    s.status = "failed"
                    self.db.add(s)
                    self.db.commit()
            except Exception:
                pass

    # ── Recruiter decision ────────────────────────────────────────────────────

    def record_recruiter_decision(
        self,
        org_id: UUID,
        screening_id: UUID,
        decision: str,
        notes: str | None,
    ) -> AIScreening:
        screening = self.get_screening(org_id, screening_id)
        screening.recruiter_decision = decision
        screening.recruiter_notes = notes
        self.db.add(screening)
        self.db.commit()
        self.db.refresh(screening)
        return screening

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete_screening(self, org_id: UUID, screening_id: UUID) -> None:
        screening = self.get_screening(org_id, screening_id)
        self.db.delete(screening)
        self.db.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _infer_seniority(candidate: Candidate | None) -> str:
    if not candidate:
        return "mid-level"
    years = getattr(candidate, "years_experience", None)
    if years is None:
        # Try parsed resume data
        parsed = getattr(candidate, "parsed_resume_data", None) or {}
        years = parsed.get("years_of_experience")
    if years is None:
        return "mid-level"
    try:
        years = float(years)
    except (TypeError, ValueError):
        return "mid-level"
    if years < 2:
        return "junior"
    elif years < 5:
        return "mid-level"
    elif years < 9:
        return "senior"
    else:
        return "lead/principal"
