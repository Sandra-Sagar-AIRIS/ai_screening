"""Exercise list_jobs + jsonable_encoder for orgs with job rows."""
from __future__ import annotations

import json
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
        rows = db.execute(
            text(
                "SELECT p.id, p.email, p.organization_id, p.role, "
                "(SELECT count(*) FROM jobs j WHERE j.organization_id = p.organization_id) AS n "
                "FROM profiles p "
                "WHERE p.organization_id IS NOT NULL "
                "ORDER BY n DESC NULLS LAST, p.created_at DESC "
                "LIMIT 5"
            )
        ).all()
    finally:
        db.close()

    for uid, email, org_id, role, n in rows:
        print(f"--- org jobs={n} role={role} email={email}")
        db2 = SessionLocal()
        try:
            user = CurrentUser(
                user_id=str(uid),
                organization_id=str(org_id),
                role=role or "admin",
                email=email or "x@x.com",
            )
            jobs = JobService(db2).list_jobs(
                UUID(str(org_id)), user, limit=200, offset=0
            )
            payload = jsonable_encoder(jobs)
            json.dumps(payload)
            print("ok", len(jobs))
        except Exception:
            traceback.print_exc()
        finally:
            db2.close()


if __name__ == "__main__":
    main()
