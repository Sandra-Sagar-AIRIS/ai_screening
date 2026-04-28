"""SMTP email sending (e.g. Brevo) for transactional messages."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from app.core.config import get_settings

logger = logging.getLogger(__name__)

SUBJECT_INVITE = "You're invited to AIRIS"


def _invite_link(token: str) -> str:
    settings = get_settings()
    base = settings.frontend_url.rstrip("/")
    return f"{base}/invite/accept?token={quote(token, safe='')}"


def send_invite_email(to_email: str, token: str) -> None:
    """
    Send invite email via SMTP (STARTTLS). Errors are logged and not raised.

    Requires SMTP_USER, SMTP_PASSWORD, SMTP_FROM, and FRONTEND_URL in settings.
    SMTP_FROM must match a verified sender in Brevo.
    """
    settings = get_settings()
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("SMTP_USER or SMTP_PASSWORD not set; skipping invite email to %s", to_email)
        return
    if not settings.smtp_from:
        logger.warning("SMTP_FROM not set; skipping invite email to %s", to_email)
        return

    link = _invite_link(token)
    body_text = (
        "You've been invited to join AIRIS. Click the link below to accept the invite.\n\n"
        f"{link}\n"
    )

    msg = EmailMessage()
    msg["Subject"] = SUBJECT_INVITE
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.set_content(body_text)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
        logger.info("Invite email sent to %s", to_email)
    except Exception:
        logger.exception("Failed to send invite email to %s", to_email)
