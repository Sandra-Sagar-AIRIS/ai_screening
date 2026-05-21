"""AIR-570/572: Automated pipeline stage-change candidate emails (COMM-005)."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.candidate_management.communication_service import CommunicationService
from app.candidate_management.models import Candidate as CMCandidate
from app.db.session import SessionLocal
from app.models.job import Job
from app.services.pipeline_stage_email_templates import (
    get_pipeline_stage_email_template,
    normalize_stage_for_pipeline_email,
)

logger = logging.getLogger(__name__)

_PIPELINE_EMAIL_QUICK_ACTION = "pipeline_stage_change"


def _pipeline_email_idempotency_key(stage_history_id: str) -> str:
    return f"ps-email-{stage_history_id}"[:120]


def run_pipeline_stage_email_notification(
    *,
    organization_id: str,
    org_id: str,
    workspace_id: str,
    candidate_id: str,
    pipeline_id: str,
    job_id: str | None,
    previous_stage: str,
    new_stage: str,
    stage_history_id: str,
    actor_user_id: str | None,
    reason: str | None = None,
) -> None:
    """
    Background worker: send one automated email per stage-history row.

    Never raises — failures are logged only.
    """
    db = SessionLocal()
    try:
        _send_pipeline_stage_email(
            db=db,
            organization_id=UUID(organization_id),
            org_id=UUID(org_id),
            workspace_id=UUID(workspace_id),
            candidate_id=UUID(candidate_id),
            pipeline_id=UUID(pipeline_id),
            job_id=UUID(job_id) if job_id else None,
            previous_stage=previous_stage,
            new_stage=new_stage,
            stage_history_id=UUID(stage_history_id),
            actor_user_id=UUID(actor_user_id) if actor_user_id else None,
            reason=reason,
        )
    except Exception:
        logger.exception(
            "pipeline_stage_email.worker_failed",
            extra={
                "pipeline_id": pipeline_id,
                "stage_history_id": stage_history_id,
                "new_stage": new_stage,
            },
        )
    finally:
        db.close()


def _send_pipeline_stage_email(
    *,
    db,
    organization_id: UUID,
    org_id: UUID,
    workspace_id: UUID,
    candidate_id: UUID,
    pipeline_id: UUID,
    job_id: UUID | None,
    previous_stage: str,
    new_stage: str,
    stage_history_id: UUID,
    actor_user_id: UUID | None,
    reason: str | None = None,
) -> None:
    stage_key = normalize_stage_for_pipeline_email(new_stage)
    if stage_key is None:
        logger.debug(
            "pipeline_stage_email.skipped_unsupported_stage pipeline_id=%s new_stage=%s",
            pipeline_id,
            new_stage,
        )
        return

    cm_candidate = db.scalar(
        select(CMCandidate).where(
            CMCandidate.id == candidate_id,
            CMCandidate.org_id == org_id,
            CMCandidate.workspace_id == workspace_id,
            CMCandidate.deleted_at.is_(None),
        )
    )
    if cm_candidate is None:
        logger.debug(
            "pipeline_stage_email.skipped_no_cm_candidate candidate_id=%s",
            candidate_id,
        )
        return

    to_email = (cm_candidate.email or "").strip()
    if not to_email:
        logger.info(
            "pipeline_stage_email.skipped_no_email candidate_id=%s pipeline_id=%s",
            candidate_id,
            pipeline_id,
        )
        return

    job_title = "the role"
    if job_id is not None:
        job = db.scalar(
            select(Job).where(Job.id == job_id, Job.organization_id == organization_id)
        )
        if job is not None and job.title:
            job_title = job.title

    template = get_pipeline_stage_email_template(
        new_stage,
        context={
            "candidate_name": cm_candidate.full_name or cm_candidate.first_name,
            "job_title": job_title,
            "company_name": "AIRIS",
            "previous_stage": previous_stage,
            "new_stage": new_stage,
            "stage_label": stage_key.replace("_", " ").title(),
            "reason": reason or "",
        },
    )
    if template is None:
        return

    user_id = actor_user_id
    if user_id is None:
        logger.warning(
            "pipeline_stage_email.skipped_no_actor_user pipeline_id=%s",
            pipeline_id,
        )
        return

    idempotency_key = _pipeline_email_idempotency_key(str(stage_history_id))
    comm = CommunicationService(db)
    try:
        comm.send_email(
            org_id=org_id,
            workspace_id=workspace_id,
            user_id=user_id,
            candidate_id=candidate_id,
            provider="smtp",
            to_email=to_email,
            subject=template.subject,
            body=template.body,
            save_as_draft=False,
            quick_action=_PIPELINE_EMAIL_QUICK_ACTION,
            attachments=[],
            template_id=None,
            template_values=None,
            idempotency_key=idempotency_key,
            pipeline_stage_notification={
                "automated": True,
                "trigger": "pipeline_stage_change",
                "pipeline_id": str(pipeline_id),
                "job_id": str(job_id) if job_id else None,
                "stage_history_id": str(stage_history_id),
                "previous_stage": previous_stage,
                "new_stage": new_stage,
                "stage_key": template.stage_key,
                "groq_enhanced": template.groq_enhanced,
            },
        )
        logger.info(
            "pipeline_stage_email.sent pipeline_id=%s stage=%s history_id=%s",
            pipeline_id,
            new_stage,
            stage_history_id,
        )
    except HTTPException as exc:
        logger.warning(
            "pipeline_stage_email.send_failed pipeline_id=%s status=%s detail=%s",
            pipeline_id,
            exc.status_code,
            exc.detail,
        )
    except Exception:
        logger.exception(
            "pipeline_stage_email.send_failed pipeline_id=%s",
            pipeline_id,
        )
