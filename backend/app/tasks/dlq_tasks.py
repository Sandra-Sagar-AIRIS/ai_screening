"""INFRA-006 / AIR-234: Dead-letter queue task.

`record_dead_letter` is the single consumer on the `deadletter` queue.
It persists the failed-task record to structured logs so it can be
inspected via Flower or any log aggregator.

No retries — dead-letter recording must not itself generate more DLQ entries.
"""
from __future__ import annotations

import logging
from typing import Any

from app.celery_app import QUEUE_DEADLETTER, celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.dlq_tasks.record_dead_letter",
    max_retries=0,
    queue=QUEUE_DEADLETTER,
    ignore_result=True,
)
def record_dead_letter(
    task_id: str = "",
    task_name: str = "",
    error: str = "",
    error_type: str = "",
    retries: int = -1,
    args: str = "",
    kwargs: str = "",
    failed_at: str = "",
    **extra: Any,
) -> None:
    """Persist a dead-lettered task to structured logs for observability."""
    logger.critical(
        "task.dead_lettered",
        extra={
            "task_id": task_id,
            "task_name": task_name,
            "error": error[:2000],
            "error_type": error_type,
            "retries": retries,
            "args_preview": args[:200],
            "kwargs_preview": kwargs[:200],
            "failed_at": failed_at,
            **{k: str(v)[:200] for k, v in extra.items()},
        },
    )
