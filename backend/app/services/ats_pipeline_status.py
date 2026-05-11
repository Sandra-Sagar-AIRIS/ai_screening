"""ATS pipeline lifecycle stored on `candidate_job_matches.ats_pipeline_status`."""

from __future__ import annotations

# Initial row or reset before deterministic write completes.
ATS_PENDING = "pending"
# Request accepted and waiting for worker execution.
ATS_QUEUED = "queued"
# Resume/profile parsing and deterministic preparation phase.
ATS_PARSING = "parsing"
# Deterministic score persisted; baseline visible to UI; semantic may be queued/running.
ATS_DETERMINISTIC_COMPLETE = "deterministic_complete"
# Background semantic worker holds the row (dedup window).
ATS_AI_ENRICHING = "ai_enriching"
# Semantic succeeded (or semantic provider absent — finalized without AI).
ATS_COMPLETED = "completed"
# Semantic provider failed; deterministic baseline remains.
ATS_FAILED = "failed"

SEMANTIC_INFLIGHT_DEDUP_SECONDS = 300
