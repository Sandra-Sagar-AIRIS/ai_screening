from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from celery import Celery
from sqlalchemy.orm import Session

from app.candidate_management.ai_adapter import HttpAIService
from app.candidate_management.models import BulkUploadItemStatus, BulkUploadStatus
from app.candidate_management.repository import CandidateRepository
from app.candidate_management.schemas import ResumeUploadRequest
from app.candidate_management.service import CandidateManagementService
from app.db.session import SessionLocal


def _build_celery_app() -> Celery:
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    backend_url = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
    return Celery("candidate_management", broker=broker_url, backend=backend_url)


celery_app = _build_celery_app()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _set_job_completed_if_finished(
    *,
    repository: CandidateRepository,
    org_id: UUID,
    workspace_id: UUID,
    job_id: UUID,
) -> None:
    pending_items = repository.list_bulk_upload_items(
        org_id=org_id,
        workspace_id=workspace_id,
        job_id=job_id,
        statuses=[BulkUploadItemStatus.PENDING, BulkUploadItemStatus.PROCESSING],
        limit=1,
        offset=0,
    )
    if pending_items:
        return
    repository.update_bulk_upload_job_status(
        org_id=org_id,
        workspace_id=workspace_id,
        job_id=job_id,
        status=BulkUploadStatus.COMPLETED,
        completed_at=_now_utc(),
    )


@celery_app.task(name="candidate_management.process_bulk_upload_item", bind=True, max_retries=3, default_retry_delay=10)
def process_bulk_upload_item(
    self,
    *,
    job_id: str,
    item_id: str,
    org_id: str,
    workspace_id: str,
) -> dict[str, Any]:
    db: Session = SessionLocal()
    try:
        org_uuid = UUID(org_id)
        workspace_uuid = UUID(workspace_id)
        bulk_job_id = UUID(job_id)
        bulk_item_id = UUID(item_id)

        repository = CandidateRepository(db)
        item = repository.get_bulk_upload_item(
            org_id=org_uuid,
            workspace_id=workspace_uuid,
            item_id=bulk_item_id,
        )
        if item is None:
            return {"success": False, "error": "BULK_UPLOAD_ITEM_NOT_FOUND", "item_id": item_id}

        repository.update_bulk_upload_job_status(
            org_id=org_uuid,
            workspace_id=workspace_uuid,
            job_id=bulk_job_id,
            status=BulkUploadStatus.PROCESSING,
            started_at=_now_utc(),
        )
        repository.update_bulk_upload_item(
            org_id=org_uuid,
            workspace_id=workspace_uuid,
            item_id=bulk_item_id,
            values={"status": BulkUploadItemStatus.PROCESSING},
        )
        db.commit()

        service = CandidateManagementService(
            db,
            repository=repository,
            ai_service=HttpAIService(),
        )
        candidate, parse_result = service.create_candidate_from_resume(
            org_id=org_uuid,
            workspace_id=workspace_uuid,
            actor_user_id=None,
            actor_role="system",
            request=ResumeUploadRequest(
                candidate_id=None,
                resume_s3_key=item.resume_s3_key or "",
                resume_file_name=item.original_file_name or "bulk_upload_resume",
            ),
        )

        repository.update_bulk_upload_item(
            org_id=org_uuid,
            workspace_id=workspace_uuid,
            item_id=bulk_item_id,
            values={
                "status": BulkUploadItemStatus.COMPLETED,
                "candidate_id": candidate.id,
                "extracted_email": candidate.email,
                "extracted_phone": candidate.phone,
                "ai_confidence": parse_result.parse_confidence,
                "parse_payload": parse_result.parsed_resume_data,
                "error_message": None,
                "details": {"result": "created"},
            },
        )
        repository.update_bulk_upload_job_counters(
            org_id=org_uuid,
            workspace_id=workspace_uuid,
            job_id=bulk_job_id,
            processed_delta=1,
            success_delta=1,
        )
        _set_job_completed_if_finished(
            repository=repository,
            org_id=org_uuid,
            workspace_id=workspace_uuid,
            job_id=bulk_job_id,
        )
        db.commit()
        return {
            "success": True,
            "job_id": job_id,
            "item_id": item_id,
            "candidate_id": str(candidate.id),
        }
    except Exception as exc:  # noqa: BLE001
        try:
            org_uuid = UUID(org_id)
            workspace_uuid = UUID(workspace_id)
            bulk_job_id = UUID(job_id)
            bulk_item_id = UUID(item_id)
            repository = CandidateRepository(db)

            error_code = "BULK_UPLOAD_FAILED"
            status_value = BulkUploadItemStatus.FAILED
            error_text = str(exc)
            if "DUPLICATE_CANDIDATE" in error_text:
                error_code = "DUPLICATE_CANDIDATE"
                status_value = BulkUploadItemStatus.SKIPPED_DUPLICATE

            repository.update_bulk_upload_item(
                org_id=org_uuid,
                workspace_id=workspace_uuid,
                item_id=bulk_item_id,
                values={
                    "status": status_value,
                    "error_message": error_text[:2000],
                    "details": {"error_code": error_code},
                },
            )
            repository.update_bulk_upload_job_counters(
                org_id=org_uuid,
                workspace_id=workspace_uuid,
                job_id=bulk_job_id,
                processed_delta=1,
                failed_delta=1 if status_value == BulkUploadItemStatus.FAILED else 0,
                skipped_delta=1 if status_value == BulkUploadItemStatus.SKIPPED_DUPLICATE else 0,
            )
            _set_job_completed_if_finished(
                repository=repository,
                org_id=org_uuid,
                workspace_id=workspace_uuid,
                job_id=bulk_job_id,
            )
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
        raise
    finally:
        db.close()


class CeleryTaskEnqueuer:
    """Service adapter that enqueues per-item bulk upload tasks."""

    def enqueue_bulk_upload_item(self, *, job_id: UUID, item_id: UUID, org_id: UUID, workspace_id: UUID) -> None:
        process_bulk_upload_item.delay(
            job_id=str(job_id),
            item_id=str(item_id),
            org_id=str(org_id),
            workspace_id=str(workspace_id),
        )

