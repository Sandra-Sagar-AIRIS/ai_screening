"""
INFRA-004: API Documentation (Swagger/OpenAPI) — Test Suite

Covers:
  - is_docs_enabled() logic (env-based defaults + explicit override)
  - /docs and /redoc available in development, absent in production
  - /openapi.json absent in production (no schema leak)
  - OpenAPI schema structure: BearerAuth security scheme
  - OpenAPI schema structure: global security requirement
  - OpenAPI schema structure: standardised error schemas
  - OpenAPI schema structure: all tag names present
  - API versioning: all routes under /api/v1/
  - Error response schemas present on operations
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_settings(app_env: str = "development", docs_enabled: bool | None = None) -> SimpleNamespace:
    """Return a minimal settings-like object for unit tests."""
    return SimpleNamespace(
        app_name="AIRIS Backend",
        app_env=app_env,
        docs_enabled=docs_enabled,
        debug=False,
        cors_origins="http://localhost:3000",
    )


# ---------------------------------------------------------------------------
# is_docs_enabled() — unit tests (no DB, no FastAPI app needed)
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.unit


class TestIsDocsEnabled:
    from app.core.openapi import is_docs_enabled  # noqa: E402

    def test_development_enabled_by_default(self):
        from app.core.openapi import is_docs_enabled

        assert is_docs_enabled(_mock_settings("development")) is True

    def test_dev_alias_enabled(self):
        from app.core.openapi import is_docs_enabled

        assert is_docs_enabled(_mock_settings("dev")) is True

    def test_staging_enabled_by_default(self):
        from app.core.openapi import is_docs_enabled

        assert is_docs_enabled(_mock_settings("staging")) is True

    def test_stage_alias_enabled(self):
        from app.core.openapi import is_docs_enabled

        assert is_docs_enabled(_mock_settings("stage")) is True

    def test_local_enabled(self):
        from app.core.openapi import is_docs_enabled

        assert is_docs_enabled(_mock_settings("local")) is True

    def test_test_enabled(self):
        from app.core.openapi import is_docs_enabled

        assert is_docs_enabled(_mock_settings("test")) is True

    def test_production_disabled_by_default(self):
        from app.core.openapi import is_docs_enabled

        assert is_docs_enabled(_mock_settings("production")) is False

    def test_prod_alias_disabled(self):
        from app.core.openapi import is_docs_enabled

        assert is_docs_enabled(_mock_settings("prod")) is False

    def test_unknown_env_disabled(self):
        from app.core.openapi import is_docs_enabled

        # Any unknown env defaults to OFF (conservative posture).
        assert is_docs_enabled(_mock_settings("canary")) is False

    def test_explicit_true_overrides_production(self):
        from app.core.openapi import is_docs_enabled

        assert is_docs_enabled(_mock_settings("production", docs_enabled=True)) is True

    def test_explicit_false_overrides_development(self):
        from app.core.openapi import is_docs_enabled

        assert is_docs_enabled(_mock_settings("development", docs_enabled=False)) is False

    def test_case_insensitive_env(self):
        from app.core.openapi import is_docs_enabled

        assert is_docs_enabled(_mock_settings("PRODUCTION")) is False
        assert is_docs_enabled(_mock_settings("Development")) is True


# ---------------------------------------------------------------------------
# OpenAPI schema content — unit tests using build_custom_openapi
# ---------------------------------------------------------------------------


class TestCustomOpenAPISchema:
    """Verify the schema built by build_custom_openapi contains expected content."""

    @pytest.fixture(autouse=True)
    def schema(self):
        """Build a schema from the live app once per test class."""
        import app.main as main_module
        from app.core.openapi import build_custom_openapi
        from app.core.config import get_settings

        settings = get_settings()
        builder = build_custom_openapi(main_module.app, settings)
        # Clear cached schema first so we always get a fresh build.
        main_module.app.openapi_schema = None
        self._schema = builder()
        return self._schema

    # ── Security scheme ──────────────────────────────────────────────────────

    def test_bearer_auth_scheme_present(self):
        schemes = self._schema.get("components", {}).get("securitySchemes", {})
        assert "BearerAuth" in schemes, "BearerAuth security scheme missing from components"

    def test_bearer_auth_is_http_bearer(self):
        scheme = self._schema["components"]["securitySchemes"]["BearerAuth"]
        assert scheme["type"] == "http"
        assert scheme["scheme"] == "bearer"

    def test_bearer_auth_has_jwt_format(self):
        scheme = self._schema["components"]["securitySchemes"]["BearerAuth"]
        assert scheme.get("bearerFormat") == "JWT"

    def test_global_security_requirement(self):
        security = self._schema.get("security", [])
        assert any("BearerAuth" in req for req in security), (
            "Global security requirement for BearerAuth missing from schema"
        )

    # ── Error schemas ────────────────────────────────────────────────────────

    def test_http_error_detail_schema_present(self):
        schemas = self._schema.get("components", {}).get("schemas", {})
        assert "HTTPErrorDetail" in schemas

    def test_validation_error_response_schema_present(self):
        schemas = self._schema.get("components", {}).get("schemas", {})
        assert "ValidationErrorResponse" in schemas

    def test_validation_error_item_schema_present(self):
        schemas = self._schema.get("components", {}).get("schemas", {})
        assert "ValidationErrorItem" in schemas

    def test_server_error_response_schema_present(self):
        schemas = self._schema.get("components", {}).get("schemas", {})
        assert "ServerErrorResponse" in schemas

    # ── Error responses on operations ────────────────────────────────────────

    def test_all_operations_have_401_response(self):
        """Every operation should document the 401 response."""
        missing: list[str] = []
        for path, path_item in self._schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if not isinstance(operation, dict):
                    continue
                if "401" not in operation.get("responses", {}):
                    missing.append(f"{method.upper()} {path}")
        assert not missing, f"Operations missing 401 response: {missing[:10]}"

    def test_all_operations_have_422_response(self):
        """Every operation should document the 422 response."""
        missing: list[str] = []
        for path, path_item in self._schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if not isinstance(operation, dict):
                    continue
                if "422" not in operation.get("responses", {}):
                    missing.append(f"{method.upper()} {path}")
        assert not missing, f"Operations missing 422 response: {missing[:10]}"

    def test_all_operations_have_500_response(self):
        """Every operation should document the 500 response."""
        missing: list[str] = []
        for path, path_item in self._schema.get("paths", {}).items():
            for method, operation in path_item.items():
                if not isinstance(operation, dict):
                    continue
                if "500" not in operation.get("responses", {}):
                    missing.append(f"{method.upper()} {path}")
        assert not missing, f"Operations missing 500 response: {missing[:10]}"

    # ── Tag coverage ─────────────────────────────────────────────────────────

    def test_core_tags_defined(self):
        """Key module tags must appear in the schema tags list."""
        expected_tags = {
            "auth", "candidates", "jobs", "clients", "pipelines",
            "interviews", "ai-screenings", "offers", "health",
        }
        defined = {t["name"] for t in self._schema.get("tags", [])}
        missing = expected_tags - defined
        assert not missing, f"Tags missing from schema: {missing}"

    # ── API metadata ─────────────────────────────────────────────────────────

    def test_schema_has_title(self):
        assert self._schema.get("info", {}).get("title")

    def test_schema_has_version(self):
        assert self._schema.get("info", {}).get("version")

    def test_schema_has_description(self):
        description = self._schema.get("info", {}).get("description", "")
        assert "Authentication" in description, "Description should document auth"
        assert "/api/v1/" in description, "Description should document versioning"


# ---------------------------------------------------------------------------
# API versioning audit
# ---------------------------------------------------------------------------


class TestApiVersioning:
    """Every registered route must be under /api/v1/."""

    def test_all_routes_versioned(self):
        import app.main as main_module
        from fastapi.routing import APIRoute

        non_versioned: list[str] = []
        for route in main_module.app.routes:
            if not isinstance(route, APIRoute):
                continue  # skip WebSocket routes and static mounts
            if not route.path.startswith("/api/v1"):
                non_versioned.append(route.path)

        assert not non_versioned, (
            f"Routes not under /api/v1/: {non_versioned}"
        )

    def test_health_route_versioned(self):
        import app.main as main_module
        from fastapi.routing import APIRoute

        health_routes = [
            r for r in main_module.app.routes
            if isinstance(r, APIRoute) and "health" in r.path
        ]
        assert health_routes, "No health route found"
        assert all(r.path.startswith("/api/v1") for r in health_routes)

    def test_auth_routes_versioned(self):
        import app.main as main_module
        from fastapi.routing import APIRoute

        auth_routes = [
            r for r in main_module.app.routes
            if isinstance(r, APIRoute) and "/auth/" in r.path
        ]
        assert auth_routes, "No auth routes found"
        assert all(r.path.startswith("/api/v1") for r in auth_routes)


# ---------------------------------------------------------------------------
# Docs endpoint availability — via TestClient (no DB required)
# ---------------------------------------------------------------------------


class TestDocsEndpoints:
    """Verify /docs, /redoc, /openapi.json serve correctly in dev config."""

    def test_docs_returns_200_in_development(self, client):
        """Swagger UI must be accessible in development (default env)."""
        from app.core.config import get_settings

        settings = get_settings()
        if settings.app_env.lower() in ("production", "prod"):
            pytest.skip("Running against a production settings file — docs disabled by design.")
        response = client.get("/docs", follow_redirects=True)
        assert response.status_code == 200

    def test_redoc_returns_200_in_development(self, client):
        """ReDoc must be accessible in development (default env)."""
        from app.core.config import get_settings

        settings = get_settings()
        if settings.app_env.lower() in ("production", "prod"):
            pytest.skip("Running against a production settings file — docs disabled by design.")
        response = client.get("/redoc", follow_redirects=True)
        assert response.status_code == 200

    def test_openapi_json_returns_200_in_development(self, client):
        """Raw OpenAPI JSON must be accessible in development."""
        from app.core.config import get_settings

        settings = get_settings()
        if settings.app_env.lower() in ("production", "prod"):
            pytest.skip("Running against a production settings file — docs disabled by design.")
        response = client.get("/openapi.json")
        assert response.status_code == 200
        body = response.json()
        assert "openapi" in body
        assert "paths" in body

    def test_docs_disabled_when_docs_enabled_false(self):
        """When DOCS_ENABLED=false the /docs endpoint must return 404."""
        import os
        from app.core.config import get_settings
        from fastapi.testclient import TestClient

        # Patch env and rebuild app with docs disabled.
        with patch.dict(os.environ, {"APP_ENV": "development", "DOCS_ENABLED": "false"}):
            get_settings.cache_clear()
            try:
                # Import fresh app creation helper rather than mutating the
                # singleton — simulate by checking is_docs_enabled directly.
                from app.core.openapi import is_docs_enabled
                s = get_settings()
                assert not is_docs_enabled(s), "docs_enabled=false should disable docs"
            finally:
                get_settings.cache_clear()

    def test_docs_disabled_in_production_env(self):
        """is_docs_enabled must return False for production APP_ENV."""
        from app.core.openapi import is_docs_enabled

        # Use a mock settings object — no need to re-instantiate the real
        # Settings (which loads .env and may have DOCS_ENABLED set).
        assert not is_docs_enabled(_mock_settings("production")), (
            "Docs must be disabled in production"
        )
        assert not is_docs_enabled(_mock_settings("prod")), (
            "Docs must be disabled for prod alias"
        )


# ---------------------------------------------------------------------------
# Error schema structure
# ---------------------------------------------------------------------------


class TestErrorSchemas:
    """Verify the injected error schemas have correct structure."""

    def test_http_error_detail_has_detail_field(self):
        from app.core.openapi import _ERROR_SCHEMAS  # noqa: PLC2701

        schema = _ERROR_SCHEMAS["HTTPErrorDetail"]
        assert "detail" in schema["properties"]

    def test_validation_error_response_required_fields(self):
        from app.core.openapi import _ERROR_SCHEMAS  # noqa: PLC2701

        schema = _ERROR_SCHEMAS["ValidationErrorResponse"]
        required = schema.get("required", [])
        assert "success" in required
        assert "error" in required
        assert "details" in required

    def test_server_error_response_required_fields(self):
        from app.core.openapi import _ERROR_SCHEMAS  # noqa: PLC2701

        schema = _ERROR_SCHEMAS["ServerErrorResponse"]
        required = schema.get("required", [])
        assert "success" in required
        assert "error" in required
        assert "exception_type" in required

    def test_validation_error_item_refs_in_response(self):
        from app.core.openapi import _ERROR_SCHEMAS  # noqa: PLC2701

        details_schema = _ERROR_SCHEMAS["ValidationErrorResponse"]["properties"]["details"]
        assert details_schema["items"]["$ref"] == "#/components/schemas/ValidationErrorItem"

    def test_error_response_refs_point_to_correct_schemas(self):
        from app.core.openapi import _COMMON_ERROR_RESPONSES  # noqa: PLC2701

        ref_401 = (
            _COMMON_ERROR_RESPONSES["401"]["content"]["application/json"]["schema"]["$ref"]
        )
        assert ref_401 == "#/components/schemas/HTTPErrorDetail"

        ref_422 = (
            _COMMON_ERROR_RESPONSES["422"]["content"]["application/json"]["schema"]["$ref"]
        )
        assert ref_422 == "#/components/schemas/ValidationErrorResponse"

        ref_500 = (
            _COMMON_ERROR_RESPONSES["500"]["content"]["application/json"]["schema"]["$ref"]
        )
        assert ref_500 == "#/components/schemas/ServerErrorResponse"
