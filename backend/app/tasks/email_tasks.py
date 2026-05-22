"""INFRA-006 / AIR-233: Async email tasks.

Replaces the synchronous send_invite_email() call in routes/invites.py.
Retries 3× with exponential backoff; permanently-failed messages route to DLQ.
"""
from __future__ import annotations

import logging
from typing import Any

from celery import Task

from app.celery_app import QUEUE_EMAIL, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.email_tasks.send_invite_email",
    bind=True,
    max_retries=3,
    retry_backoff=True,       # 10s → 20s → 40s
    retry_backoff_max=120,
    retry_jitter=True,
    queue=QUEUE_EMAIL,
    time_limit=60,
)
def send_invite_email_task(self: Task, to_email: str, token: str) -> dict[str, Any]:
    """Send an invite email asynchronously.

    Args:
        to_email: Recipient email address.
        token:    Invite token used to build the accept-link.
    """
    try:
        from app.services.email_service import send_invite_email

        send_invite_email(to_email, token)
        logger.info("email_tasks.invite_sent", extra={"to": to_email})
        return {"status": "sent", "to": to_email}
    except Exception as exc:
        logger.warning(
            "email_tasks.invite_send_failed",
            extra={"to": to_email, "error": str(exc)[:300], "retries": self.request.retries},
        )
        raise self.retry(exc=exc) from exc


@celery_app.task(
    name="app.tasks.email_tasks.send_generic_email",
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=120,
    retry_jitter=True,
    queue=QUEUE_EMAIL,
    time_limit=60,
)
def send_generic_email_task(
    self: Task,
    to_email: str,
    subject: str,
    body_text: str,
) -> dict[str, Any]:
    """Send a plain-text transactional email asynchronously."""
    try:
        import smtplib
        from email.message import EmailMessage

        from app.core.config import get_settings

        settings = get_settings()
        if not settings.smtp_user or not settings.smtp_password or not settings.smtp_from:
            raise RuntimeError("SMTP credentials not configured.")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to_email
        msg.set_content(body_text)

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)

        logger.info("email_tasks.generic_sent", extra={"to": to_email, "subject": subject[:80]})
        return {"status": "sent", "to": to_email}
    except Exception as exc:
        logger.warning(
            "email_tasks.generic_send_failed",
            extra={"to": to_email, "error": str(exc)[:300], "retries": self.request.retries},
        )
        raise self.retry(exc=exc) from exc
