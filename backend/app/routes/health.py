from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])
settings = get_settings()
logger = logging.getLogger(__name__)


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, env=settings.app_env)


@router.get("/health/workers")
def worker_health() -> dict[str, Any]:
    """INFRA-006: Report Celery worker liveness and active task counts.

    Returns a 200 response regardless of broker state so that load-balancer
    health checks are not affected by a temporarily unavailable Redis.
    """
    try:
        from app.celery_app import celery_app

        inspector = celery_app.control.inspect(timeout=2.0)
        ping_reply: dict | None = inspector.ping()
        active_reply: dict | None = inspector.active()

        if not ping_reply:
            return {"status": "no_workers", "worker_count": 0, "active_tasks": 0}

        worker_count = len(ping_reply)
        active_tasks = sum(len(tasks) for tasks in (active_reply or {}).values())
        workers = [
            {
                "name": name,
                "active": len((active_reply or {}).get(name, [])),
            }
            for name in ping_reply
        ]
        return {
            "status": "ok",
            "worker_count": worker_count,
            "active_tasks": active_tasks,
            "workers": workers,
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning("worker_health: broker unreachable — %s", exc)
        return {"status": "broker_unavailable", "worker_count": 0, "active_tasks": 0, "error": str(exc)[:200]}

