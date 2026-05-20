"""
PIPE-008: Background scheduler for offer expiry alerts.

Uses a daemon threading.Timer (no external scheduler dependency) to run the
expiry check 5 minutes after startup, then every 24 hours.

Start by calling `start_offer_expiry_scheduler()` from the FastAPI startup event.
Stop by calling `stop_offer_expiry_scheduler()` (e.g. in a shutdown hook).
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_INITIAL_DELAY_SECONDS = 300       # 5 min after startup
_INTERVAL_SECONDS = 86_400         # 24 hours

_timer: threading.Timer | None = None
_lock = threading.Lock()


def _run_expiry_check() -> None:
    """Execute one expiry-alert scan, then reschedule the next."""
    try:
        from app.db.session import SessionLocal
        from app.services.offer_service import OfferService

        db = SessionLocal()
        try:
            svc = OfferService(db)
            count = svc.process_expiry_alerts()
            logger.info("offer_expiry_scheduler.cycle_complete alerts_sent=%d", count)
        finally:
            db.close()
    except Exception:
        logger.exception("offer_expiry_scheduler.cycle_failed — will retry next cycle")
    finally:
        # Always reschedule so a single failure doesn't kill the scheduler.
        _schedule_next(_INTERVAL_SECONDS)


def _schedule_next(delay: float) -> None:
    global _timer
    with _lock:
        t = threading.Timer(delay, _run_expiry_check)
        t.daemon = True
        t.start()
        _timer = t


def start_offer_expiry_scheduler() -> None:
    """
    Start the offer expiry background scheduler.

    Safe to call multiple times — subsequent calls are no-ops if the
    scheduler is already running.
    """
    with _lock:
        if _timer is not None and _timer.is_alive():
            logger.debug("offer_expiry_scheduler.already_running — skipped")
            return

    logger.info(
        "offer_expiry_scheduler.starting initial_delay_s=%d interval_s=%d",
        _INITIAL_DELAY_SECONDS,
        _INTERVAL_SECONDS,
    )
    _schedule_next(_INITIAL_DELAY_SECONDS)


def stop_offer_expiry_scheduler() -> None:
    """Cancel any pending expiry check (e.g. on application shutdown)."""
    global _timer
    with _lock:
        if _timer is not None:
            _timer.cancel()
            _timer = None
            logger.info("offer_expiry_scheduler.stopped")
