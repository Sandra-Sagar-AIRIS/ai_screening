"""Probe GET /api/v1/jobs — prints status and traceback on failure."""
from __future__ import annotations

import traceback

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import create_access_token
from app.db.session import SessionLocal
from app.main import app


def probe(role: str | None = None) -> None:
    db = SessionLocal()
    try:
        if role:
            row = db.execute(
                text(
                    "SELECT id, email, organization_id, role FROM profiles "
                    "WHERE lower(role) = :role ORDER BY created_at DESC LIMIT 1"
                ),
                {"role": role.lower()},
            ).first()
        else:
            row = db.execute(
                text(
                    "SELECT id, email, organization_id, role FROM profiles "
                    "ORDER BY created_at DESC LIMIT 1"
                )
            ).first()
    finally:
        db.close()

    if not row:
        print(f"no profile for role={role!r}")
        return

    user_id, email, org_id, prof_role = row
    token = create_access_token(
        subject=str(user_id),
        extra_claims={"organization_id": str(org_id), "role": prof_role or "admin"},
    )
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(
        "/api/v1/jobs?limit=200&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    print(f"role={prof_role} status={r.status_code}")
    if r.status_code >= 400:
        print(r.text[:1200])
    else:
        print("ok", len(r.json()))


def main() -> None:
    for role in (None, "admin", "recruiter", "vendor", "client"):
        try:
            probe(role)
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    main()
