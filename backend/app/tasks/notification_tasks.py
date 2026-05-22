"""INFRA-006 / AIR-233: Candidate notification tasks.

Dispatched when a candidate's pipeline stage or application status changes.
Uses the `notifications` queue so it doesn't compete with AI or email workers.
"""
from __future__ import annotations

import logging
from typing import Any

from celery import Task

from app.celery_app import QUEUE_NOTIFICATIONS, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.notification_tasks.notify_stage_change",
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    queue=QUEUE_NOTIFICATIONS,
    time_limit=60,
)
def notify_stage_change_task(
    self: Task,
    *,
    candidate_id: str,
    candidate_email: str,
    stage: str,
    job_title: str,
    org_id: str,
) -> dict[str, Any]:
    """Notify a candidate that their application stage has changed.

    Currently sends an email notification; extend to push/SMS as needed.
    """
    try:
        from app.tasks.email_tasks import send_generic_email_task

        subject = f"Update on your application — {job_title}"
        body = (
            f"Hi,\n\n"
            f"Your application for {job_title} has been updated to stage: {stage}.\n\n"
            "Log in to AIRIS to see more details.\n"
        )
        send_generic_email_task.apply_async(
            kwargs={"to_email": candidate_email, "subject": subject, "body_text": body},
            queue="email",
        )
        logger.info(
            "notification_tasks.stage_change_queued",
            extra={"candidate_id": candidate_id, "stage": stage, "org_id": org_id},
        )
        return {"status": "queued", "candidate_id": candidate_id, "stage": stage}
    except Exception as exc:
        logger.warning(
            "notification_tasks.stage_change_failed",
            extra={"candidate_id": candidate_id, "error": str(exc)[:300]},
        )
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="app.tasks.notification_tasks.notify_bulk_stage_change",
    bind=True,
    max_retries=2,
    retry_backoff=True,
    queue=QUEUE_NOTIFICATIONS,
    time_limit=300,
)
def notify_bulk_stage_change_task(
    self: Task,
    *,
    candidate_ids: list[str],
    stage: str,
    job_title: str,
    org_id: str,
) -> dict[str, Any]:
    """Enqueue individual stage-change notifications for a batch of candidates."""
    try:
        from uuid import UUID

        from sqlalchemy import select

        from app.db.session import SessionLocal
        from app.models.candidate import Candidate

        db = SessionLocal()
        try:
            uuids = [UUID(cid) for cid in candidate_ids]
            candidates = list(
                db.scalars(select(Candidate).where(Candidate.id.in_(uuids)))
            )
        finally:
            db.close()

        queued = 0
        for candidate in candidates:
            if candidate.email:
                notify_stage_change_task.apply_async(
                    kwargs={
                        "candidate_id": str(candidate.id),
                        "candidate_email": candidate.email,
                        "stage": stage,
                        "job_title": job_title,
                        "org_id": org_id,
                    },
                    queue=QUEUE_NOTIFICATIONS,
                )
                queued += 1

        return {"status": "queued", "count": queued}
    except Exception as exc:
        raise self.retry(exc=exc) from exc
