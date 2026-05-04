from __future__ import annotations

import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

import app.main as main_module
from app.core.dependencies import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.organization import Organization
from app.schemas.auth import CurrentUser


class DummyDB:
    def scalar(self, *_args, **_kwargs):
        return None


def _dummy_db_override() -> Generator[DummyDB, None, None]:
    yield DummyDB()


def _load_test_env() -> None:
    load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env.test")))


def _run_migrations_on_test_db() -> None:
    alembic_ini_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg = Config(alembic_ini_path)
    test_db_url = os.getenv("TEST_DATABASE_URL")
    if not test_db_url:
        pytest.skip("TEST_DATABASE_URL is required for DB integration tests.")

    previous_database_url = os.getenv("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_db_url
    get_settings.cache_clear()
    try:
        command.upgrade(cfg, "bootstrap@head")
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        get_settings.cache_clear()


def _is_integration_test(request: pytest.FixtureRequest) -> bool:
    return request.node.get_closest_marker("integration") is not None


@pytest.fixture(scope="session")
def setup_test_database() -> Generator[None, None, None]:
    from tests.db import test_engine
    if test_engine is None:
        pytest.skip("TEST_DATABASE_URL is required for DB integration tests.")

    _load_test_env()
    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    _run_migrations_on_test_db()
    yield
    with test_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    test_engine.dispose()


@pytest.fixture()
def db_session(setup_test_database: None) -> Generator[Session, None, None]:
    from tests.db import TestingSessionLocal

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(request: pytest.FixtureRequest) -> Generator[TestClient, None, None]:
    main_module.reflect_database_schema = lambda: None

    if _is_integration_test(request):
        db_session = request.getfixturevalue("db_session")

        def _test_db_override() -> Generator[Session, None, None]:
            yield db_session

        main_module.app.dependency_overrides[get_db] = _test_db_override
    else:
        main_module.app.dependency_overrides[get_db] = _dummy_db_override

    with TestClient(main_module.app) as test_client:
        yield test_client
    main_module.app.dependency_overrides.pop(get_db, None)


@pytest.fixture()
def auth_headers(request: pytest.FixtureRequest) -> dict[str, str]:
    if _is_integration_test(request):
        db_session = request.getfixturevalue("db_session")
        organization = Organization(name=f"Test Org {uuid4().hex[:8]}")
        db_session.add(organization)
        db_session.commit()
        db_session.refresh(organization)
        organization_id = str(organization.id)
    else:
        organization_id = "22222222-2222-2222-2222-222222222222"

    return {
        "X-User-Id": "11111111-1111-1111-1111-111111111111",
        "X-Organization-Id": organization_id,
        "X-User-Role": "recruiter",
    }


@pytest.fixture()
def authenticated_user_override() -> CurrentUser:
    return CurrentUser(
        user_id="11111111-1111-1111-1111-111111111111",
        organization_id="22222222-2222-2222-2222-222222222222",
        role="admin",
    )


@pytest.fixture()
def force_auth(client: TestClient, authenticated_user_override: CurrentUser) -> Generator[None, None, None]:
    def _override_user() -> CurrentUser:
        return authenticated_user_override

    main_module.app.dependency_overrides[get_current_user] = _override_user
    yield
    main_module.app.dependency_overrides.pop(get_current_user, None)
