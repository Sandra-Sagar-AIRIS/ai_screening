from __future__ import annotations

from uuid import UUID

from app.candidate_management.tasks import celery_app
from app.db.session import SessionLocal


def run_rescore_candidate_job(*, organization_id: str, candidate_id: str, job_id: str) -> dict[str, str]:
    from app.services.job_service import JobService

    db = SessionLocal()
    try:
        service = JobService(db)
        service.rescore_candidate_job_sync(
            organization_id=UUID(organization_id),
            candidate_id=UUID(candidate_id),
            job_id=UUID(job_id),
        )
        service._refresh_job_match_cache(job_id=UUID(job_id), organization_id=UUID(organization_id))
        db.commit()
        return {"status": "ok", "candidate_id": candidate_id, "job_id": job_id}
    finally:
        db.close()


def run_rescore_job(*, organization_id: str, job_id: str) -> dict[str, str]:
    from app.services.job_service import JobService

    db = SessionLocal()
    try:
        service = JobService(db)
        service.rescore_job_sync(
            organization_id=UUID(organization_id),
            job_id=UUID(job_id),
        )
        db.commit()
        return {"status": "ok", "job_id": job_id}
    finally:
        db.close()


def run_rescore_candidate(*, organization_id: str, candidate_id: str) -> dict[str, str]:
    from app.services.job_service import JobService

    db = SessionLocal()
    try:
        service = JobService(db)
        service.rescore_candidate_sync(
            organization_id=UUID(organization_id),
            candidate_id=UUID(candidate_id),
        )
        db.commit()
        return {"status": "ok", "candidate_id": candidate_id}
    finally:
        db.close()


@celery_app.task(name="ats.rescore_candidate_job", bind=True, max_retries=3, default_retry_delay=10)
def rescore_candidate_job_task(self, *, organization_id: str, candidate_id: str, job_id: str) -> dict[str, str]:  # noqa: ARG001
    return run_rescore_candidate_job(
        organization_id=organization_id,
        candidate_id=candidate_id,
        job_id=job_id,
    )


@celery_app.task(name="ats.rescore_job", bind=True, max_retries=3, default_retry_delay=10)
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

