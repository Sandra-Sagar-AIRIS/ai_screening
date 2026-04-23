# PostgreSQL Integration Testing

## 1) Start ephemeral PostgreSQL

```bash
docker compose -f docker-compose.test.yml up -d
```

Service details:
- image: `postgres:15`
- db: `airis_test_db`
- user: `test_user`
- port: `5433`

## 2) Configure test database URL

Copy `.env.test.example` values into your environment:

```bash
set TEST_DATABASE_URL=postgresql+psycopg://test_user:test_password@localhost:5433/airis_test_db
```

On PowerShell:

```powershell
$env:TEST_DATABASE_URL="postgresql+psycopg://test_user:test_password@localhost:5433/airis_test_db"
```

## 3) Run integration tests

From `backend/`:

```bash
..\.venv\Scripts\python -m pytest -q
```

What happens automatically:
- Alembic migrations run to `head` before tests.
- Tests use a real SQLAlchemy engine connected to `TEST_DATABASE_URL`.
- At session end, test schema is dropped and recreated.

## 4) Stop ephemeral PostgreSQL

```bash
docker compose -f docker-compose.test.yml down -v
```
