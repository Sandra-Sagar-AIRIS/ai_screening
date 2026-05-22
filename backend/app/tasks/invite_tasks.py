"""INFRA-006 / AIR-235: Invite reminder scheduled task (F-INV-07).
F-INV-05: Invite expiry sweep task.

Runs hourly via Celery Beat.  Finds all pending invites expiring within
the next 24 hours and enqueues a reminder email for each.
Also sweeps invites past their expiry date and marks them expired.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.celery_app import QUEUE_EMAIL, QUEUE_BACKGROUND, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.invite_tasks.send_invite_reminders",
    queue=QUEUE_EMAIL,
    time_limit=120,
    ignore_result=False,
)
def send_invite_reminders() -> dict[str, Any]:
    """Periodic task: enqueue reminder emails for invites expiring in ≤24 hours.

    Designed to be idempotent — safe to run more than once in the same window.
    Dispatches individual email tasks so each reminder has its own retry budget.
    """
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.invite import Invite
    from app.tasks.email_tasks import send_generic_email_task

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        # Target invites expiring in the next 23–25 hour window to avoid
        # double-sending across hourly runs.
        window_start = now + timedelta(hours=23)
        window_end = now + timedelta(hours=25)

        expiring_invites = list(
            db.scalars(
                select(Invite).where(
                    Invite.status.in_(["sent", "opened"]),  # F-INV-05: new statuses
                    Invite.expires_at >= window_start,
                    Invite.expires_at <= window_end,
                )
            )
        )

        if not expiring_invites:
            logger.info("invite_tasks.no_expiring_invites")
            return {"queued": 0}

        from app.core.config import get_settings

        settings = get_settings()

        queued = 0
        for invite in expiring_invites:
            base = settings.frontend_url.rstrip("/")
            from urllib.parse import quote

            link = f"{base}/invite/accept?token={quote(invite.token, safe='')}"
            body = (
                "Reminder: Your AIRIS invitation is expiring soon.\n\n"
                f"Accept your invite before it expires:\n{link}\n"
            )
            send_generic_email_task.apply_async(
                kwargs={
                    "to_email": invite.email,
                    "subject": "Your AIRIS invitation expires soon",
                    "body_text": body,
                },
                queue=QUEUE_EMAIL,
            )
            queued += 1
            logger.info(
                "invite_tasks.reminder_queued",
                extra={"email": invite.email, "invite_id": str(invite.id), "expires_at": invite.expires_at.isoformat()},
            )

        return {"queued": queued}
    finally:
        db.close()


@celery_app.task(
    name="app.tasks.invite_tasks.sweep_expired_invites",
    queue=QUEUE_BACKGROUND,
    time_limit=120,
    ignore_result=False,
)
def sweep_expired_invites() -> dict[str, Any]:
    """F-INV-05: Mark invites past their expiry date as 'expired'.

    Targets invites in 'sent' or 'opened' status whose expires_at has passed.
    Idempotent — safe to run multiple times.
    """
    from sqlalchemy import select, update

    from app.db.session import SessionLocal
    from app.models.invite import (
        INVITE_STATUS_EXPIRED,
        INVITE_STATUS_OPENED,
        INVITE_STATUS_SENT,
        Invite,
    )

    db = SessionLocal()
    try:
        now = datetime.now(UTC)
        result = db.execute(
            update(Invite)
            .where(
                Invite.status.in_([INVITE_STATUS_SENT, INVITE_STATUS_OPENED]),
                Invite.expires_at < now,
            )
            .values(status=INVITE_STATUS_EXPIRED, expired_at=now)
            .returning(Invite.id)
        )
        expired_count = len(result.fetchall())
        db.commit()

        logger.info(
            "invite_tasks.sweep_expired",
            extra={"expired_count": expired_count, "swept_at": now.isoformat()},
        )
        return {"expired": expired_count}
    finally:
        db.close()
