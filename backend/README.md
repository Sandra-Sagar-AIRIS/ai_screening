# AIRIS Backend Scaffold

Production-oriented FastAPI backend scaffold with:
- modular architecture (`app/models`, `app/schemas`, `app/routes`, `app/services`, `app/db`)
- SQLAlchemy + PostgreSQL (Supabase-compatible)
- env-based DB config (`DATABASE_URL`)
- Alembic migration setup with baseline for existing DB
- runtime schema reflection (read-only, no DB structure changes)

## 1) Setup

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set `DATABASE_URL` in `.env`.

## 2) Run API

```bash
uvicorn app.main:app --reload
```

Health endpoint:
- `GET /api/v1/health`

## 3) Reflection (existing Supabase schema)

At startup, `app.models.reflected.reflect_database_schema()` reflects your current DB schema into ORM classes using SQLAlchemy automap.

Optional: generate a quick snapshot of reflected models:

```bash
python scripts/generate_reflection_snapshot.py
```

## 4) Alembic Workflow

This project is configured for an existing database.

### First-time baseline on existing DB

```bash
alembic stamp head
```

This marks the database at baseline revision without modifying tables.

### Generate future migrations

```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

### Migration safety rules

- Do not run raw SQL DDL manually for tracked schema changes.
- Always create a migration file, review it, then apply via Alembic.
- Validate on staging before production.

