"""Print traceback for GET /api/v1/jobs if it fails."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app


def main() -> None:
    db = SessionLocal()
    row = db.execute(
        text(
            "SELECT id, organization_id, role FROM profiles "
            "WHERE lower(role) = 'admin' AND organization_id IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 1"
        )
    ).first()
    db.close()
    if not row:
        print("no admin profile")
        return

    user_id, org_id, role = row
    token = create_access_token(
        subject=str(user_id),
        extra_claims={"organization_id": str(org_id), "role": role or "admin"},
    )
    client = TestClient(app, raise_server_exceptions=True)
    client.get(
        "/api/v1/jobs?limit=200&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    print("ok")


if __name__ == "__main__":
    main()
