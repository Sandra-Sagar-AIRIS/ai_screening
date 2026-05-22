"""INFRA-006 / AIR-233: Async AI task queue (AI-001, AI-002).

Covers:
  - AI sourcing session execution (AI-SOURCE-001, previously run via ThreadPoolExecutor)
  - ATS candidate rescore (previously blocking the API thread)

Both run on the `ai` queue with tighter concurrency to protect LLM rate limits.
"""
from __future__ import annotations

import logging
from typing import Any

from celery import Task

from app.celery_app import QUEUE_AI, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.ai_tasks.run_sourcing_session",
    bind=True,
    max_retries=1,              # Sourcing is expensive; retry once only
    retry_backoff=True,
    retry_backoff_max=60,
    queue=QUEUE_AI,
    time_limit=900,             # 15 min hard limit — provider calls can be slow
    soft_time_limit=840,
)
def run_sourcing_session_task(
    self: Task,
    *,
    session_id: str,
    org_id: str,
    jd_text: str,
) -> dict[str, Any]:
    """Execute an AI sourcing session end-to-end.

    Replaces the ThreadPoolExecutor dispatch in task_runner.py when
    CELERY_DISPATCH_ENABLED=true.
    """
    try:
        from app.services.sourcing.runner import run_sourcing_session

        run_sourcing_session(session_id=session_id, org_id=org_id, jd_text=jd_text)
        logger.info("ai_tasks.sourcing_complete", extra={"session_id": session_id})
        return {"status": "complete", "session_id": session_id}
    except Exception as exc:
        logger.warning(
            "ai_tasks.sourcing_failed",
            extra={"session_id": session_id, "error": str(exc)[:300], "retries": self.request.retries},
        )
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="app.tasks.ai_tasks.rescore_candidate",
    bind=True,
    max_retries=2,
    retry_backoff=True,
    retry_backoff_max=60,
    queue=QUEUE_AI,
    time_limit=300,
    soft_time_limit=270,
)
def rescore_candidate_task(
    self: Task,
    *,
    org_id: str,
    candidate_id: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Run ATS + semantic rescore for a candidate asynchronously.

    Returns a summary dict; callers poll /candidates/{id}/matches for results.
    """
    try:
        from uuid import UUID

        from app.db.session import SessionLocal
        from app.services.job_service import JobService

        db = SessionLocal()
        try:
            svc = JobService(db)
            pairs = svc.rescore_candidate_fast(
                organization_id=UUID(org_id),
                candidate_id=UUID(candidate_id),
                job_id=UUID(job_id) if job_id else None,
            )
            db.commit()
        finally:
            db.close()

        logger.info(
            "ai_tasks.rescore_complete",
            extra={"candidate_id": candidate_id, "pairs": pairs},
        )
        return {"status": "complete", "candidate_id": candidate_id, "pairs_scored": pairs}
    except Exception as exc:
        logger.warning(
            "ai_tasks.rescore_failed",
            extra={"candidate_id": candidate_id, "error": str(exc)[:300], "retries": self.request.retries},
        )
        raise self.retry(exc=exc) from exc
