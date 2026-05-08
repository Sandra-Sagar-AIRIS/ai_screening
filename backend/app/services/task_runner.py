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
        logger.exception("Fallback task execution failed")


def dispatch_task(
    *,
    task: Any | None,
    fallback: Callable[..., Any],
    kwargs: dict[str, Any],
) -> None:
    """Best-effort async dispatch.

    1) If a Celery task is provided and has `.delay`, enqueue it.
    2) If enqueue fails (broker down, serialization errors, etc.), run fallback
       in a detached background worker so request latency stays low.
    """
    if task is not None and hasattr(task, "delay"):
        try:
            task.delay(**kwargs)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Celery dispatch failed; using detached fallback: %s", exc)
    _FALLBACK_EXECUTOR.submit(_run_fallback_safely, fallback=fallback, kwargs=kwargs)

