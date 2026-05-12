from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

logger = logging.getLogger(__name__)
_FALLBACK_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="airis-task-fallback")


def _run_fallback_safely(*, fallback: Callable[..., Any], kwargs: dict[str, Any]) -> None:
    try:
        fallback(**kwargs)
    except Exception:  # noqa: BLE001
        logger.exception(
            "task_runner.fallback_failed",
            extra={
                "fallback": getattr(fallback, "__name__", str(fallback)),
                "kwargs_keys": sorted(kwargs.keys()),
                **{k: str(v) for k, v in kwargs.items() if k in ("organization_id", "candidate_id", "job_id")},
            },
        )


def _dispatch_in_worker(task: Any | None, fallback: Callable[..., Any], kwargs: dict[str, Any]) -> None:
    """Runs Celery enqueue (or fallback) off the HTTP thread.

    Celery's ``.delay()`` can block for a long time when the broker is slow or
    unreachable; never call it on the request thread.
    """
    if task is not None and hasattr(task, "delay"):
        try:
            task.delay(**kwargs)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "task_runner.celery_dispatch_failed",
                extra={
                    "error": str(exc)[:500],
                    "exception_class": type(exc).__name__,
                    "kwargs_keys": sorted(kwargs.keys()),
                },
            )
    _run_fallback_safely(fallback=fallback, kwargs=kwargs)


def dispatch_task(
    *,
    task: Any | None,
    fallback: Callable[..., Any],
    kwargs: dict[str, Any],
) -> None:
    """Best-effort async dispatch (never blocks the caller on broker I/O).

    Celery enqueue and in-process fallback both run on a small thread pool so
    FastAPI can return immediately after the DB commit.
    """
    _FALLBACK_EXECUTOR.submit(_dispatch_in_worker, task, fallback, kwargs)

