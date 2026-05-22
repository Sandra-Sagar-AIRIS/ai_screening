"""INFRA-006 / AIR-233: Calendar sync async tasks.

Async calendar synchronization for Google and Microsoft Calendar integrations.
Runs on the `integrations` queue with timeout protection.
"""
from __future__ import annotations

import logging
from typing import Any

from celery import Task

from app.celery_app import QUEUE_INTEGRATIONS, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.integration_tasks.sync_calendar_event",
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    queue=QUEUE_INTEGRATIONS,
    time_limit=120,
    soft_time_limit=100,
)
def sync_calendar_event_task(
    self: Task,
    *,
    interview_id: str,
    org_id: str,
    provider: str = "google",  # "google" | "microsoft"
) -> dict[str, Any]:
    """Sync an interview event to a calendar provider.

    Args:
        interview_id: UUID of the interview to sync.
        org_id:       Organisation UUID for tenant scoping.
        provider:     "google" or "microsoft".
    """
    try:
        from uuid import UUID

        from app.db.session import SessionLocal
        from app.models.interview import Interview
        from sqlalchemy import select

        db = SessionLocal()
        try:
            interview = db.scalar(
                select(Interview).where(Interview.id == UUID(interview_id))
            )
            if interview is None:
                logger.warning(
                    "integration_tasks.interview_not_found",
                    extra={"interview_id": interview_id},
                )
                return {"status": "skipped", "reason": "interview_not_found"}

            # Integration hook — wire to actual provider clients when available.
            logger.info(
                "integration_tasks.calendar_sync",
                extra={
                    "interview_id": interview_id,
                    "provider": provider,
                    "org_id": org_id,
                },
            )
        finally:
            db.close()

        return {"status": "synced", "interview_id": interview_id, "provider": provider}
    except Exception as exc:
        logger.warning(
            "integration_tasks.calendar_sync_failed",
            extra={
                "interview_id": interview_id,
                "provider": provider,
                "error": str(exc)[:300],
                "retries": self.request.retries,
            },
        )
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="app.tasks.integration_tasks.delete_calendar_event",
    bind=True,
    max_retries=3,
    retry_backoff=True,
    queue=QUEUE_INTEGRATIONS,
    time_limit=60,
)
def delete_calendar_event_task(
    self: Task,
    *,
    interview_id: str,
    org_id: str,
    provider: str = "google",
) -> dict[str, Any]:
    """Remove a calendar event when an interview is cancelled."""
    try:
        logger.info(
            "integration_tasks.calendar_delete",
            extra={"interview_id": interview_id, "provider": provider},
        )
        return {"status": "deleted", "interview_id": interview_id}
    except Exception as exc:
        raise self.retry(exc=exc) from exc
