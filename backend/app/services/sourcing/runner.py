"""Sourcing session runner — background task.

Orchestrates: query generation → provider search → dedup → scoring → persist results.
Called via task_runner.dispatch_task; runs on the fallback thread pool.
"""
from __future__ import annotations

import asyncio
import logging
import time
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.sourcing_session import SourcingResult, SourcingSession
from app.services.sourcing.deduplicator import CandidateDeduplicator
from app.services.sourcing.providers.airis_provider import AirisCandidateProvider
from app.services.sourcing.providers.naukri_stub import NaukriStubProvider
from app.services.sourcing.providers.base import SourcingQuery, RawCandidate
from app.services.sourcing.scorer import CandidateScoringService, ScoredCandidate

logger = logging.getLogger(__name__)


def run_sourcing_session(*, session_id: str, org_id: str, jd_text: str) -> None:
    """Entry point for background execution.

    Creates its own DB session (runs off the HTTP thread).
    """
    db = SessionLocal()
    try:
        _execute(db=db, session_id=UUID(session_id), org_id=UUID(org_id), jd_text=jd_text)
    except Exception:
        logger.exception(
            "sourcing.runner.unhandled_error",
            extra={"session_id": session_id, "org_id": org_id},
        )
        _mark_failed(SessionLocal(), UUID(session_id), "Unhandled runner error")
    finally:
        db.close()


def _execute(db: Session, session_id: UUID, org_id: UUID, jd_text: str) -> None:
    t0 = time.monotonic()

    # ── Mark running ──────────────────────────────────────────────────────────
    db.execute(
        update(SourcingSession)
        .where(SourcingSession.id == session_id)
        .values(status="running")
    )
    db.commit()

    try:
        session_row = db.get(SourcingSession, session_id)
        if not session_row:
            logger.error("sourcing.runner.session_not_found", extra={"session_id": str(session_id)})
            return

        query: SourcingQuery = _query_from_snapshot(session_row)

        # ── Gather from providers ─────────────────────────────────────────────
        raw_candidates: list[RawCandidate] = []

        providers_used: list[str] = session_row.providers_used or ["airis", "naukri_stub"]

        if "airis" in providers_used:
            airis = AirisCandidateProvider(db)
            airis_results = asyncio.get_event_loop().run_until_complete(
                airis.search(query, org_id, limit=20)
            ) if asyncio.get_event_loop().is_closed() else _run_sync(airis.search(query, org_id, limit=20))
            raw_candidates.extend(airis_results)
            logger.info(
                "sourcing.runner.provider_done",
                extra={"provider": "airis", "count": len(airis_results), "session_id": str(session_id)},
            )

        if "naukri_stub" in providers_used:
            naukri = NaukriStubProvider()
            naukri_results = _run_sync(naukri.search(query, org_id, limit=10))
            raw_candidates.extend(naukri_results)
            logger.info(
                "sourcing.runner.provider_done",
                extra={"provider": "naukri_stub", "count": len(naukri_results), "session_id": str(session_id)},
            )

        # ── Dedup ─────────────────────────────────────────────────────────────
        dedup = CandidateDeduplicator()
        unique_candidates = dedup.deduplicate(raw_candidates)

        # ── Score ─────────────────────────────────────────────────────────────
        scorer = CandidateScoringService(jd_text=jd_text)
        scored: list[ScoredCandidate] = _run_sync(scorer.score_batch(unique_candidates))

        # ── Persist results ───────────────────────────────────────────────────
        for s in scored:
            row = SourcingResult(
                session_id=session_id,
                organization_id=org_id,
                external_id=s.external_id,
                source=s.source,
                first_name=s.first_name,
                last_name=s.last_name,
                email=s.email,
                phone=s.phone,
                location=s.location,
                title=s.title,
                skills=s.skills or [],
                ats_score=s.ats_score,
                ats_tier=s.ats_tier,
                semantic_score=s.semantic_score,
                recruiter_summary=s.recruiter_summary,
                matched_skills=s.matched_skills or [],
                is_duplicate=s.is_duplicate,
                raw_data=s.raw_data or {},
            )
            db.add(row)

        duration_ms = int((time.monotonic() - t0) * 1000)
        db.execute(
            update(SourcingSession)
            .where(SourcingSession.id == session_id)
            .values(status="complete", total_results=len(scored))
        )
        db.commit()

        logger.info(
            "sourcing.session.completed",
            extra={
                "session_id": str(session_id),
                "org_id": str(org_id),
                "total_results": len(scored),
                "duration_ms": duration_ms,
            },
        )

    except Exception as exc:
        db.rollback()
        logger.exception(
            "sourcing.runner.execution_error",
            extra={"session_id": str(session_id)},
        )
        _mark_failed(db, session_id, str(exc)[:500])


def _mark_failed(db: Session, session_id: UUID, error: str) -> None:
    try:
        db.execute(
            update(SourcingSession)
            .where(SourcingSession.id == session_id)
            .values(status="failed", error_detail=error)
        )
        db.commit()
        logger.error(
            "sourcing.session.failed",
            extra={"session_id": str(session_id), "error": error},
        )
    except Exception:
        logger.exception("sourcing.runner.mark_failed_error")
    finally:
        db.close()


def _query_from_snapshot(session_row: SourcingSession) -> SourcingQuery:
    """Rebuild SourcingQuery from the stored JSON snapshot."""
    snap: dict = session_row.query_snapshot or {}
    return SourcingQuery(
        title=snap.get("title", ""),
        skills=snap.get("skills", []),
        keywords=snap.get("keywords", []),
        location=snap.get("location"),
        experience_min=snap.get("experience_min"),
        experience_max=snap.get("experience_max"),
    )


def _run_sync(coro) -> list:
    """Run a coroutine synchronously (for thread-executor context)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=60)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)
