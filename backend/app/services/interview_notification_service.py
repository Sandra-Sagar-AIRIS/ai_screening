from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)


class InterviewNotificationService:
    """
    Notification hooks for interview lifecycle events.

    Each method is a clean integration point for email/Slack/calendar
    notifications. They are called from InterviewService after the DB
    write commits but run fire-and-forget (no await / no exception
    propagation) so a broken notification never rolls back a DB change.

    Implementation: swap logger.info stubs with actual send logic
    (e.g. Celery task, FastAPI BackgroundTask, or direct SMTP call).
    """

    def on_interview_scheduled(self, interview_id: UUID, organization_id: UUID) -> None:
        logger.info(
            "interview_notification.scheduled",
            extra={"interview_id": str(interview_id), "organization_id": str(organization_id)},
        )

    def on_interview_confirmed(self, interview_id: UUID, organization_id: UUID) -> None:
        logger.info(
            "interview_notification.confirmed",
            extra={"interview_id": str(interview_id), "organization_id": str(organization_id)},
        )

    def on_interview_rescheduled(self, interview_id: UUID, organization_id: UUID) -> None:
        logger.info(
            "interview_notification.rescheduled",
            extra={"interview_id": str(interview_id), "organization_id": str(organization_id)},
        )

    def on_interview_cancelled(self, interview_id: UUID, organization_id: UUID) -> None:
        logger.info(
            "interview_notification.cancelled",
            extra={"interview_id": str(interview_id), "organization_id": str(organization_id)},
        )

    def on_feedback_submitted(self, interview_id: UUID, organization_id: UUID) -> None:
        logger.info(
            "interview_notification.feedback_submitted",
            extra={"interview_id": str(interview_id), "organization_id": str(organization_id)},
        )
