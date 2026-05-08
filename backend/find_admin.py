import os
from sqlalchemy import create_engine, text

database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is required.")

engine = create_engine(database_url, hide_parameters=True, future=True)

with engine.connect() as conn:
    result = conn.execute(text("SELECT id, organization_id, role FROM profiles WHERE role='admin' LIMIT 1"))
    admin = result.fetchone()
    if admin:
        print(f"ADMIN_ID={admin[0]}")
        print(f"ORG_ID={admin[1]}")
    else:
        print("No admin found")
