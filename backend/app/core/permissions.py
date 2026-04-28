from __future__ import annotations

from collections.abc import Iterable

# Permission constants (action-based RBAC).
CANDIDATES_CREATE = "candidates:create"
CANDIDATES_READ = "candidates:read"
CANDIDATES_UPDATE = "candidates:update"
CANDIDATES_DELETE = "candidates:delete"

JOBS_CREATE = "jobs:create"
JOBS_READ = "jobs:read"
JOBS_UPDATE = "jobs:update"
JOBS_DELETE = "jobs:delete"

PIPELINE_UPDATE = "pipeline:update"
PIPELINE_READ = "pipeline:read"
PIPELINE_CREATE = "pipeline:create"

INTERVIEWS_CREATE = "interviews:create"
INTERVIEWS_READ = "interviews:read"
INTERVIEWS_UPDATE = "interviews:update"

ORGANIZATION_MANAGE = "organization:manage"
USERS_INVITE = "users:invite"

CLIENTS_CREATE = "clients:create"
CLIENTS_READ = "clients:read"
CLIENTS_UPDATE = "clients:update"

ALL_PERMISSIONS: tuple[str, ...] = (
    CANDIDATES_CREATE,
    CANDIDATES_READ,
    CANDIDATES_UPDATE,
    CANDIDATES_DELETE,
    JOBS_CREATE,
    JOBS_READ,
    JOBS_UPDATE,
    JOBS_DELETE,
    PIPELINE_UPDATE,
    PIPELINE_READ,
    PIPELINE_CREATE,
    INTERVIEWS_CREATE,
    INTERVIEWS_READ,
    INTERVIEWS_UPDATE,
    ORGANIZATION_MANAGE,
    USERS_INVITE,
    CLIENTS_CREATE,
    CLIENTS_READ,
    CLIENTS_UPDATE,
)


def normalize_permissions(values: Iterable[str]) -> list[str]:
    allowed = set(ALL_PERMISSIONS)
    normalized = []
    for value in values:
        permission = value.strip().lower()
        if permission in allowed:
            normalized.append(permission)
    return sorted(set(normalized))
