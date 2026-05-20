"""
OpenAPI / Swagger / ReDoc configuration for AIRIS.

Responsibilities
----------------
* ``is_docs_enabled(settings)``  — decide whether /docs and /redoc are served.
* ``OPENAPI_TAGS``               — ordered tag objects with descriptions for the UI.
* ``build_custom_openapi(app, settings)`` — returns a callable that FastAPI uses as
  ``app.openapi``.  The callable builds and caches a schema that adds:
    - BearerAuth (JWT) security scheme in ``components.securitySchemes``
    - Global ``security`` requirement (applies to all operations)
    - Standardised error response schemas in ``components.schemas``
    - Common error responses (400/401/403/404/409/422/500) on every path/method
    - Rich API metadata (description, version)

Production safety
-----------------
``is_docs_enabled`` returns ``False`` for ``APP_ENV=production`` (or ``prod``).
This causes ``FastAPI(docs_url=None, redoc_url=None, openapi_url=None)`` so no
documentation UI or raw schema endpoint is exposed.  Override with
``DOCS_ENABLED=true`` in the environment for intentional production access.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from app.core.config import Settings

# ---------------------------------------------------------------------------
# Environments where interactive API docs are ON by default
# ---------------------------------------------------------------------------

_DOCS_ON_ENVS: frozenset[str] = frozenset(
    {"development", "dev", "staging", "stage", "local", "test"}
)

# ---------------------------------------------------------------------------
# API metadata
# ---------------------------------------------------------------------------

API_VERSION = "1.0.0"

API_DESCRIPTION = """\
## AIRIS Recruitment Platform API

AI-powered recruitment platform providing candidate tracking, job management,
interview scheduling, AI-driven screening, and pipeline automation.

---

### Authentication

All protected endpoints require a **Bearer token** in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

Obtain a token:
```http
POST /api/v1/auth/login
Content-Type: application/json

{"email": "user@example.com", "password": "s3cr3t"}
```

Refresh an expired access token:
```http
POST /api/v1/auth/refresh
Content-Type: application/json

{"refresh_token": "<refresh_token>"}
```

Click the **Authorize** button (🔒) in Swagger UI to enter your token once and
have it applied to all requests automatically.

---

### API Versioning

All endpoints are served under the `/api/v1/` base path.

---

### Error Responses

| Status | Meaning |
|--------|---------|
| `400`  | Bad Request — invalid input or domain rule violation |
| `401`  | Unauthorized — missing, expired, or invalid Bearer token |
| `403`  | Forbidden — valid token but insufficient RBAC permissions |
| `404`  | Not Found — resource does not exist or org-scope mismatch |
| `409`  | Conflict — duplicate resource (e.g. duplicate client name) |
| `422`  | Unprocessable Entity — request body failed Pydantic validation |
| `500`  | Internal Server Error — unhandled exception |
"""

# ---------------------------------------------------------------------------
# Tag metadata (controls ordering and descriptions in Swagger UI / ReDoc)
# ---------------------------------------------------------------------------

OPENAPI_TAGS: list[dict] = [
    {
        "name": "auth",
        "description": "Authentication — signup, login, token refresh, and logout.",
    },
    {
        "name": "me",
        "description": "Current-user profile, effective permissions, and session info.",
    },
    {
        "name": "candidates",
        "description": (
            "Candidate profiles — create, read, update, resume upload, "
            "ATS rescoring, and AI screening triggers."
        ),
    },
    {
        "name": "jobs",
        "description": (
            "Job postings — create, publish, submit candidates, "
            "track submissions, and manage vendor access."
        ),
    },
    {
        "name": "clients",
        "description": (
            "Client workspaces — create clients, assign recruiters, "
            "update details, and soft-delete (archive)."
        ),
    },
    {
        "name": "pipelines",
        "description": (
            "Pipeline entries — stage transitions, status changes, "
            "offer management, and history tracking."
        ),
    },
    {
        "name": "pipeline-analytics",
        "description": "Pipeline analytics — KPI metrics, funnel data, and CSV export.",
    },
    {
        "name": "applications",
        "description": "Job applications — submission workflow between candidates and jobs.",
    },
    {
        "name": "interviews",
        "description": (
            "Interview scheduling — create, update, claim, submit feedback, "
            "and obtain LiveKit video room tokens."
        ),
    },
    {
        "name": "interview-copilot",
        "description": (
            "AI Interview Copilot — on-demand GPT-powered suggestions "
            "for active interviewers."
        ),
    },
    {
        "name": "interview-copilot-ws",
        "description": (
            "AI Interview Copilot WebSocket — real-time event stream "
            "(JWT passed as `?token=` query param; not testable via Swagger UI)."
        ),
    },
    {
        "name": "ai-screenings",
        "description": (
            "AI Screening — GPT-powered automated candidate evaluations "
            "with scored Q&A and recommendations."
        ),
    },
    {
        "name": "ats",
        "description": (
            "Applicant Tracking System — semantic resume enrichment, "
            "skill extraction, and job-match scoring."
        ),
    },
    {
        "name": "offers",
        "description": (
            "Offer management — extend, accept, reject, withdraw, "
            "and expire pipeline offers (PIPE-008)."
        ),
    },
    {
        "name": "vendor",
        "description": (
            "Vendor portal — staffing-vendor job listings "
            "and candidate submission tracking."
        ),
    },
    {
        "name": "invites",
        "description": "Team invitations — send, resend, accept, and revoke org invite emails.",
    },
    {
        "name": "users",
        "description": "User management — list, update roles, and deactivate organisation members.",
    },
    {
        "name": "roles",
        "description": "RBAC roles — create, update, and manage role-to-permission assignments.",
    },
    {
        "name": "permissions",
        "description": "Permission catalog — enumerate all available RBAC permission codes.",
    },
    {
        "name": "dashboard",
        "description": (
            "Dashboard — aggregated KPIs, pipeline stage counts, "
            "recent jobs, and activity feed (single round-trip)."
        ),
    },
    {
        "name": "health",
        "description": "Health check — API liveness probe for load-balancers and monitoring.",
    },
]

# ---------------------------------------------------------------------------
# Security scheme
# ---------------------------------------------------------------------------

_BEARER_SCHEME: dict = {
    "BearerAuth": {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": (
            "JWT access token obtained from `POST /api/v1/auth/login`. "
            "Include in requests as: `Authorization: Bearer <token>`."
        ),
    }
}

# ---------------------------------------------------------------------------
# Standardised error component schemas (injected into components.schemas)
# ---------------------------------------------------------------------------

_ERROR_SCHEMAS: dict[str, dict] = {
    "HTTPErrorDetail": {
        "type": "object",
        "title": "HTTPErrorDetail",
        "description": (
            "Generic HTTP error response returned for 400 / 401 / 403 / 404 / 409. "
            "The `detail` field is a plain string for simple errors or a structured "
            "dict for domain errors (e.g. conflict codes)."
        ),
        "properties": {
            "detail": {
                "oneOf": [
                    {"type": "string"},
                    {"type": "object"},
                    {"type": "array", "items": {}},
                ],
                "description": "Human-readable error detail.",
                "examples": [
                    "Invalid credentials.",
                    {"error": "CLIENT_NAME_CONFLICT", "message": "A client with this name already exists."},
                ],
            }
        },
        "required": ["detail"],
        "example": {"detail": "Invalid credentials."},
    },
    "ValidationErrorItem": {
        "type": "object",
        "title": "ValidationErrorItem",
        "description": "Single field-level validation error (Pydantic v2 format).",
        "properties": {
            "loc": {
                "type": "array",
                "items": {"oneOf": [{"type": "string"}, {"type": "integer"}]},
                "description": "Error location path — list of field names and/or array indices.",
                "example": ["body", "email"],
            },
            "msg": {
                "type": "string",
                "description": "Human-readable validation failure message.",
            },
            "type": {
                "type": "string",
                "description": "Pydantic v2 error type code (e.g. 'value_error', 'missing').",
            },
        },
        "required": ["loc", "msg", "type"],
        "example": {
            "loc": ["body", "email"],
            "msg": "value is not a valid email address",
            "type": "value_error.email",
        },
    },
    "ValidationErrorResponse": {
        "type": "object",
        "title": "ValidationErrorResponse",
        "description": (
            "422 Unprocessable Entity — returned by the RequestValidationError handler "
            "when request body or query parameters fail Pydantic validation."
        ),
        "properties": {
            "success": {"type": "boolean", "default": False},
            "error": {"type": "string", "default": "Validation Error"},
            "details": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/ValidationErrorItem"},
                "description": "One item per failing field.",
            },
        },
        "required": ["success", "error", "details"],
        "example": {
            "success": False,
            "error": "Validation Error",
            "details": [
                {
                    "loc": ["body", "email"],
                    "msg": "value is not a valid email address",
                    "type": "value_error.email",
                }
            ],
        },
    },
    "ServerErrorResponse": {
        "type": "object",
        "title": "ServerErrorResponse",
        "description": (
            "500 Internal Server Error — returned by the global Exception handler "
            "for unhandled exceptions.  The `error` field is a safe, truncated "
            "representation of the exception message (max 2 000 characters)."
        ),
        "properties": {
            "success": {"type": "boolean", "default": False},
            "detail": {
                "type": "string",
                "default": "Internal server error",
                "description": "Top-level error description.",
            },
            "error": {
                "type": "string",
                "description": "Truncated exception message.",
            },
            "exception_type": {
                "type": "string",
                "description": "Python exception class name.",
            },
        },
        "required": ["success", "detail", "error", "exception_type"],
        "example": {
            "success": False,
            "detail": "Internal server error",
            "error": "Unexpected condition encountered",
            "exception_type": "RuntimeError",
        },
    },
}

# Common error responses injected into every operation (setdefault — won't
# overwrite any response codes already declared on individual routes).
_COMMON_ERROR_RESPONSES: dict[str, dict] = {
    "400": {
        "description": "Bad Request",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/HTTPErrorDetail"}
            }
        },
    },
    "401": {
        "description": "Unauthorized — missing or invalid Bearer token",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/HTTPErrorDetail"}
            }
        },
    },
    "403": {
        "description": "Forbidden — insufficient RBAC permissions",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/HTTPErrorDetail"}
            }
        },
    },
    "404": {
        "description": "Not Found",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/HTTPErrorDetail"}
            }
        },
    },
    "409": {
        "description": "Conflict — duplicate or conflicting resource",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/HTTPErrorDetail"}
            }
        },
    },
    "422": {
        "description": "Unprocessable Entity — request validation failure",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ValidationErrorResponse"}
            }
        },
    },
    "500": {
        "description": "Internal Server Error",
        "content": {
            "application/json": {
                "schema": {"$ref": "#/components/schemas/ServerErrorResponse"}
            }
        },
    },
}

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def is_docs_enabled(settings: "Settings") -> bool:
    """Return ``True`` if Swagger UI and ReDoc should be served.

    Decision order:
    1. ``settings.docs_enabled`` if explicitly set via the ``DOCS_ENABLED``
       environment variable (allows per-deployment override).
    2. Enabled for development / staging / local / test environments.
    3. Disabled for production / prod (to avoid exposing the schema publicly).
    """
    if settings.docs_enabled is not None:
        return settings.docs_enabled
    return settings.app_env.strip().lower() in _DOCS_ON_ENVS


def build_custom_openapi(app: "FastAPI", settings: "Settings"):
    """Return a callable that FastAPI uses as ``app.openapi``.

    The callable builds the schema once and caches it on
    ``app.openapi_schema``.  Subsequent calls return the cached copy.

    Schema additions vs. FastAPI defaults
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    * ``components.securitySchemes.BearerAuth`` — HTTP Bearer / JWT scheme.
    * ``security`` (global) — applies BearerAuth to every operation by default.
    * ``components.schemas`` — standardised error models (HTTPErrorDetail, etc.)
    * Per-operation ``responses`` — 400/401/403/404/409/422/500 on every path
      (using ``setdefault`` so hand-crafted responses on individual routes
      are never overwritten).
    """
    from fastapi.openapi.utils import get_openapi

    def _openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=settings.app_name,
            version=API_VERSION,
            description=API_DESCRIPTION,
            routes=app.routes,
            tags=OPENAPI_TAGS,
        )

        # ── Security scheme ──────────────────────────────────────────────────
        components = schema.setdefault("components", {})
        components.setdefault("securitySchemes", {}).update(_BEARER_SCHEME)

        # ── Global security requirement ──────────────────────────────────────
        # Marks every operation as requiring BearerAuth by default.
        # Public endpoints (login, signup, health) don't actually enforce it —
        # FastAPI's dependency system handles real auth — but the UI renders
        # the lock icon consistently, which is the desired documentation UX.
        schema.setdefault("security", [{"BearerAuth": []}])

        # ── Error schemas ────────────────────────────────────────────────────
        components.setdefault("schemas", {}).update(_ERROR_SCHEMAS)

        # ── Common error responses on every operation ────────────────────────
        for path_item in schema.get("paths", {}).values():
            for operation in path_item.values():
                if not isinstance(operation, dict):
                    continue
                existing_responses = operation.setdefault("responses", {})
                for status_code, response_obj in _COMMON_ERROR_RESPONSES.items():
                    existing_responses.setdefault(status_code, response_obj)

        app.openapi_schema = schema
        return schema

    return _openapi
