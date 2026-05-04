from app.db.session import engine
from sqlalchemy import text

with engine.begin() as conn:
    before = conn.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num")).fetchall()
    print("before:", before)

    conn.execute(text("DELETE FROM alembic_version"))
    conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260429_0001')"))

    after = conn.execute(text("SELECT version_num FROM alembic_version ORDER BY version_num")).fetchall()
    print("after:", after)
