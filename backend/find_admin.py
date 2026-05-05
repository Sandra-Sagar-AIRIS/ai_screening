import uuid
from sqlalchemy import create_engine, text

engine = create_engine("postgresql://postgres:postgres@localhost:5432/airis")

with engine.connect() as conn:
    result = conn.execute(text("SELECT id, organization_id, role FROM profiles WHERE role='admin' LIMIT 1"))
    admin = result.fetchone()
    if admin:
        print(f"ADMIN_ID={admin[0]}")
        print(f"ORG_ID={admin[1]}")
    else:
        print("No admin found")
