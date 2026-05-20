"""Hit GET /jobs through FastAPI app (auth + permissions + json)."""
from __future__ import annotations

import json
import traceback
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.dependencies import get_current_user
from app.db.session import SessionLocal
from app.main import app
from app.schemas.auth import CurrentUser
from app.services.permission_service import PermissionService


def main() -> None:
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT id, email, organization_id, role FROM profiles "
                "WHERE email = 'sandra@sipra.com' LIMIT 1"
            )
        ).first()
        if not row:
            row = db.execute(
                text(
                    "SELECT id, email, organization_id, role FROM profiles "
                    "WHERE organization_id IS NOT NULL ORDER BY created_at DESC LIMIT 1"
                )
            ).first()
    finally:
        db.close()

    if not row:
        print("no profile")
        return

    uid, email, org_id, role = row
    user = CurrentUser(
        user_id=str(uid),
        organization_id=str(org_id),
        role=role or "admin",
        email=email or "",
    )

    db2 = SessionLocal()
    try:
        perms = PermissionService(db2).get_user_permissions(str(uid))
        print("perms has jobs:read", "jobs:read" in perms, "count", len(perms))
    finally:
        db2.close()

    def _override_user():
        return user

    app.dependency_overrides[get_current_user] = _override_user
    try:
        with TestClient(app) as client:
            r = client.get("/api/v1/jobs?limit=100&offset=0")
            print("status", r.status_code)
            if r.status_code != 200:
                print(r.text[:2000])
            else:
                data = r.json()
                print("ok jobs", len(data) if isinstance(data, list) else type(data))
    except Exception:
        traceback.print_exc()
    finally:
        app.dependency_overrides.pop(get_current_user, None)


if __name__ == "__main__":
    main()
