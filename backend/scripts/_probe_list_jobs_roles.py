"""list_jobs for each role — service layer only."""
from __future__ import annotations

import traceback
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy import text

from app.db.session import SessionLocal
from app.schemas.auth import CurrentUser
from app.services.job_service import JobService


def probe_role(db, role: str) -> None:
    row = db.execute(
        text(
            "SELECT id, email, organization_id, role FROM profiles "
            "WHERE lower(role) = :role AND organization_id IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 1"
        ),
        {"role": role.lower()},
    ).first()
    if not row:
        print(f"{role}: no profile")
        return
    user = CurrentUser(
        user_id=str(row[0]),
        organization_id=str(row[2]),
        role=row[3] or role,
    )
    try:
        jobs = JobService(db).list_jobs(UUID(user.organization_id), user, limit=200, offset=0)
        jsonable_encoder(jobs)
        print(f"{role}: ok count={len(jobs)}")
    except Exception as exc:
        print(f"{role}: FAIL {exc}")
        traceback.print_exc()


def main() -> None:
    db = SessionLocal()
    try:
        for role in ("admin", "recruiter", "vendor", "client"):
            probe_role(db, role)
    finally:
        db.close()


if __name__ == "__main__":
    main()
