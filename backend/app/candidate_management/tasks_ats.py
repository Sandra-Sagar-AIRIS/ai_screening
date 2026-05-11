from __future__ import annotations

import logging
import time
from uuid import UUID

from sqlalchemy import select

from app.candidate_management.tasks import celery_app
from app.db.session import SessionLocal
from app.models.job import Job

logger = logging.getLogger(__name__)


def _set_job_enrichment_status(*, organization_id: UUID, job_id: UUID, status: str) -> None:
    """Persist pipeline visibility without touching the main task transaction."""
    db = SessionLocal()
    try:
        row = db.scalar(select(Job).where(Job.id == job_id, Job.organization_id == organization_id))
        if row is not None:
            row.enrichment_status = status
            db.add(row)
            db.commit()
    except Exception:
        logger.exception(
            "ats.task.enrichment_status_update_failed",
            extra={"organization_id": str(organization_id), "job_id": str(job_id), "status": status},
        )
        db.rollback()
    finally:
        db.close()


def run_rescore_candidate_job(*, organization_id: str, candidate_id: str, job_id: str) -> dict[str, str]:
    from app.services.job_service import JobService

    t0 = time.monotonic()
    db = SessionLocal()
    oid = UUID(organization_id)
    cid = UUID(candidate_id)
    jid = UUID(job_id)
    extra_base = {
        "ats_phase": "rescore_candidate_job",
        "organization_id": organization_id,
        "candidate_id": candidate_id,
        "job_id": job_id,
    }
    try:
        service = JobService(db)
        service.rescore_candidate_job_deterministic_sync(organization_id=oid, candidate_id=cid, job_id=jid)
        service._refresh_job_match_cache(job_id=jid, organization_id=oid)
        service.dispatch_enrich_candidate_job_semantic(organization_id=oid, candidate_id=cid, job_id=jid)
        db.commit()
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "ats.task.ok",
            extra={**extra_base, "duration_ms": duration_ms},
        )
        return {"status": "ok", "candidate_id": candidate_id, "job_id": job_id}
    except Exception:
        logger.exception(
            "ats.task.failed",
            extra={
                **extra_base,
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "exception_class": "see_traceback",
            },
        )
        db.rollback()
        raise
    finally:
        db.close()


def run_enrich_candidate_job_semantic(
    *,
    organization_id: str,
    candidate_id: str,
    job_id: str,
    enqueued_at: str | None = None,
) -> dict[str, str]:
    from app.services.job_service import JobService

    t0 = time.monotonic()
    db = SessionLocal()
    oid = UUID(organization_id)
    cid = UUID(candidate_id)
    jid = UUID(job_id)
    extra_base = {
        "ats_phase": "enrich_candidate_job_semantic",
        "organization_id": organization_id,
        "candidate_id": candidate_id,
        "job_id": job_id,
    }
    queue_delay_ms: int | None = None
    if enqueued_at:
        try:
            from datetime import datetime, timezone

            enqueue_dt = datetime.fromisoformat(enqueued_at)
            if enqueue_dt.tzinfo is None:
                enqueue_dt = enqueue_dt.replace(tzinfo=timezone.utc)
            queue_delay_ms = max(0, int((datetime.now(timezone.utc) - enqueue_dt).total_seconds() * 1000))
        except Exception:
            queue_delay_ms = None
    try:
        service = JobService(db)
        service.enrich_candidate_job_semantic_sync(organization_id=oid, candidate_id=cid, job_id=jid)
        service._refresh_job_match_cache(job_id=jid, organization_id=oid)
        db.commit()
        logger.info(
            "ats.task.ok",
            extra={
                **extra_base,
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "queue_delay_ms": queue_delay_ms,
            },
        )
        return {"status": "ok", "candidate_id": candidate_id, "job_id": job_id}
    except Exception:
        logger.exception(
            "ats.task.failed",
            extra={**extra_base, "duration_ms": int((time.monotonic() - t0) * 1000)},
        )
        db.rollback()
        raise
    finally:
        db.close()


def run_rescore_job(*, organization_id: str, job_id: str) -> dict[str, str]:
    from app.services.job_service import JobService

    t0 = time.monotonic()
    db = SessionLocal()
    oid = UUID(organization_id)
    jid = UUID(job_id)
    extra_base = {"ats_phase": "rescore_job", "organization_id": organization_id, "job_id": job_id}
    try:
        service = JobService(db)
        t_rescore0 = time.monotonic()
        service.rescore_job_sync(
            organization_id=oid,
            job_id=jid,
        )
        rescore_ms = int((time.monotonic() - t_rescore0) * 1000)
        row = db.scalar(select(Job).where(Job.id == jid, Job.organization_id == oid))
        if row is not None:
            row.enrichment_status = "ready"
            db.add(row)
        db.commit()
        logger.info(
            "ats.task.ok",
            extra={
                **extra_base,
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "rescore_sync_ms": rescore_ms,
            },
        )
        return {"status": "ok", "job_id": job_id}
    except Exception:
        logger.exception(
            "ats.task.failed",
            extra={
                **extra_base,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )
        db.rollback()
        _set_job_enrichment_status(organization_id=oid, job_id=jid, status="failed")
        raise
    finally:
        db.close()


def run_rescore_candidate(*, organization_id: str, candidate_id: str) -> dict[str, str]:
    from app.services.job_service import JobService

    t0 = time.monotonic()
    db = SessionLocal()
    extra_base = {"ats_phase": "rescore_candidate", "organization_id": organization_id, "candidate_id": candidate_id}
    try:
        service = JobService(db)
        service.rescore_candidate_sync(
            organization_id=UUID(organization_id),
            candidate_id=UUID(candidate_id),
        )
        db.commit()
        logger.info(
            "ats.task.ok",
            extra={**extra_base, "duration_ms": int((time.monotonic() - t0) * 1000)},
        )
        return {"status": "ok", "candidate_id": candidate_id}
    except Exception:
        logger.exception(
            "ats.task.failed",
            extra={
                **extra_base,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )
        db.rollback()
        raise
    finally:
        db.close()


@celery_app.task(name="ats.rescore_candidate_job", bind=True, max_retries=3, default_retry_delay=10)
def rescore_candidate_job_task(self, *, organization_id: str, candidate_id: str, job_id: str) -> dict[str, str]:  # noqa: ARG001
    return run_rescore_candidate_job(
        organization_id=organization_id,
        candidate_id=candidate_id,
        job_id=job_id,
    )


@celery_app.task(
    name="ats.rescore_job",
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    soft_time_limit=600,
    time_limit=660,
)
def rescore_job_task(self, *, organization_id: str, job_id: str) -> dict[str, str]:  # noqa: ARG001
    return run_rescore_job(
        organization_id=organization_id,
        job_id=job_id,
    )


@celery_app.task(name="ats.rescore_candidate", bind=True, max_retries=3, default_retry_delay=10)
def rescore_candidate_task(self, *, organization_id: str, candidate_id: str) -> dict[str, str]:  # noqa: ARG001
    return run_rescore_candidate(
        organization_id=organization_id,
        candidate_id=candidate_id,
    )


@celery_app.task(name="ats.enrich_candidate_job_semantic", bind=True, max_retries=3, default_retry_delay=15)
def enrich_candidate_job_semantic_task(  # noqa: ARG001
    self,
    *,
    organization_id: str,
    candidate_id: str,
    job_id: str,
    enqueued_at: str | None = None,
) -> dict[str, str]:
    if enqueued_at:
        try:
            from datetime import datetime, timezone

            enqueue_dt = datetime.fromisoformat(enqueued_at)
            if enqueue_dt.tzinfo is None:
                enqueue_dt = enqueue_dt.replace(tzinfo=timezone.utc)
            queue_delay_ms = int((datetime.now(timezone.utc) - enqueue_dt).total_seconds() * 1000)
            logger.info(
                "ats.queue.delay",
                extra={
                    "ats_phase": "enrich_candidate_job_semantic",
                    "organization_id": organization_id,
                    "candidate_id": candidate_id,
                    "job_id": job_id,
                    "queue_delay_ms": max(0, queue_delay_ms),
                },
            )
        except Exception:
            logger.debug("ats.queue.delay_parse_failed", exc_info=False)
    return run_enrich_candidate_job_semantic(
        organization_id=organization_id,
        candidate_id=candidate_id,
        job_id=job_id,
        enqueued_at=enqueued_at,
    )
