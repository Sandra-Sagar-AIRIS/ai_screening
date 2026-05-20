"""Reproduce list_jobs failure."""
import traceback
from uuid import UUID

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.job import Job
from app.schemas.auth import CurrentUser
from app.services.job_service import JobService

ORG = None  # set from first job if needed


def main() -> None:
    db = SessionLocal()
    try:
        first_org = db.scalar(select(Job.organization_id).limit(1))
        if not first_org:
            print("No jobs in DB")
            return
        org_id = first_org
        print("org_id", org_id)
        user = CurrentUser(
            user_id="00000000-0000-0000-0000-000000000001",
            organization_id=str(org_id),
            role="admin",
            permissions=[],
        )
        service = JobService(db)
        jobs = service.list_jobs(UUID(str(org_id)), user, limit=100, offset=0)
        print("ok count", len(jobs))
        from fastapi.encoders import jsonable_encoder

        encoded = jsonable_encoder(jobs)
        print("jsonable_encoder ok", len(encoded))
    except Exception:
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
