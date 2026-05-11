"""Short TTL caches to trim redundant DB reads during ATS hot paths."""

from __future__ import annotations

import time
from collections.abc import Callable
from uuid import UUID

_JOB_SKILLS_TTL_SEC = 60.0
_RESUME_EXTRA_TTL_SEC = 45.0

_job_skills_cache: dict[UUID, tuple[float, list[str], list[str]]] = {}
_resume_extra_cache: dict[UUID, tuple[float, dict[str, object]]] = {}


def get_job_skills_cached(
    job_id: UUID,
    *,
    loader: Callable[[], tuple[list[str], list[str]]],
) -> tuple[list[str], list[str]]:
    now = time.monotonic()
    hit = _job_skills_cache.get(job_id)
    if hit and now - hit[0] < _JOB_SKILLS_TTL_SEC:
        return hit[1], hit[2]
    req, pref = loader()
    _job_skills_cache[job_id] = (now, req, pref)
    return req, pref


def get_resume_extra_cached(
    candidate_id: UUID,
    *,
    loader: Callable[[], dict[str, object]],
) -> dict[str, object]:
    now = time.monotonic()
    hit = _resume_extra_cache.get(candidate_id)
    if hit and now - hit[0] < _RESUME_EXTRA_TTL_SEC:
        return hit[1]
    data = loader()
    _resume_extra_cache[candidate_id] = (now, data)
    return data


def invalidate_job_skills(job_id: UUID) -> None:
    _job_skills_cache.pop(job_id, None)


def invalidate_resume_extra(candidate_id: UUID) -> None:
    _resume_extra_cache.pop(candidate_id, None)
