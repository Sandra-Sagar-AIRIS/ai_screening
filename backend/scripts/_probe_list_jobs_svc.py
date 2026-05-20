"""Reproduce list_jobs without loading full FastAPI app."""
from __future__ import annotations

import traceback
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import text

from app.db.session import SessionLocal
from app.schemas.auth import CurrentUser
from app.services.job_service import JobService


def main() -> None:
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT id, email, organization_id, role FROM profiles "
                "WHERE organization_id IS NOT NULL "
                "ORDER BY created_at DESC LIMIT 1"
            )
        ).first()
        if not row:
            print("no profile")
            return
        user = CurrentUser(
            user_id=str(row[0]),
            organization_id=str(row[2]),
            role=row[3] or "admin",
            email=row[1],
        )
        svc = JobService(db)
        jobs = svc.list_jobs(UUID(user.organization_id), user, limit=200, offset=0)
        print("jobs", len(jobs))
        enc = jsonable_encoder(jobs)
        print("encoded", len(enc))
    except Exception:
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
