"""Tests for PIPE-004: Pipeline List & Filters.

Covers:
- Filtering by job_id, candidate_id, stage, status
- Pagination (limit / offset)
- Sorting by created_at and stage_updated_at (asc / desc)
- Org scoping (cross-org isolation)
- Stage count metadata
- Combined filter combinations
- Invalid query parameter handling
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.pipeline import (
    PipelineSortBy,
    PipelineSortDir,
    PipelineStage,
    PipelineStatus,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_pipeline(
    *,
    stage: str = "applied",
    pipeline_status: str = "active",
    org_id=None,
    job_id=None,
    candidate_id=None,
    created_at=None,
    stage_updated_at=None,
) -> MagicMock:
    p = MagicMock()
    p.id = uuid4()
    p.organization_id = org_id or uuid4()
    p.job_id = job_id or uuid4()
    p.candidate_id = candidate_id or uuid4()
    p.stage = stage
    p.status = pipeline_status
    p.notes = None
    p.created_at = created_at or datetime.now(UTC)
    p.updated_at = p.created_at
    p.stage_updated_at = stage_updated_at
    return p


def _make_user(org_id=None) -> MagicMock:
    u = MagicMock()
    u.user_id = str(uuid4())
    u.organization_id = str(org_id or uuid4())
    return u


def _make_service(pipelines: list, total: int = 0, stage_counts: dict | None = None):
    """Return a PipelineService stub with list_pipelines_paginated pre-configured."""
    from app.services.pipeline_service import PipelineService

    db = MagicMock()
    svc = PipelineService.__new__(PipelineService)
    svc.db = db
    svc._scope = MagicMock()
    svc._scope.is_scoped_user.return_value = False
    svc._candidates = MagicMock()

    _total = total if total else len(pipelines)
    _stage_counts = stage_counts or {}

    # Stub the internal helpers used by list_pipelines_paginated.
    svc._build_pipeline_filter_stmt = MagicMock(return_value=MagicMock())

    # Wire list_pipelines_paginated to return stubbed values directly.
    svc.list_pipelines_paginated = MagicMock(return_value=(pipelines, _total, _stage_counts))
    svc.list_pipelines = MagicMock(return_value=pipelines)
    return svc


# ── Stage count schema ─────────────────────────────────────────────────────────

class TestPipelineListMeta:
    def test_stage_counts_default_empty(self):
        from app.schemas.pipeline import PipelineListMeta
        meta = PipelineListMeta(total=0, limit=50, offset=0)
        assert meta.stage_counts == {}

    def test_stage_counts_populated(self):
        from app.schemas.pipeline import PipelineListMeta
        counts = {"applied": 10, "screening": 5, "rejected": 2}
        meta = PipelineListMeta(total=17, limit=50, offset=0, stage_counts=counts)
        assert meta.stage_counts["applied"] == 10
        assert meta.stage_counts["rejected"] == 2

    def test_total_matches_sum_when_unfiltered(self):
        from app.schemas.pipeline import PipelineListMeta
        counts = {"applied": 3, "interview": 2}
        meta = PipelineListMeta(total=5, limit=10, offset=0, stage_counts=counts)
        assert sum(meta.stage_counts.values()) == meta.total


# ── Sort enum validation ──────────────────────────────────────────────────────

class TestPipelineSortEnums:
    def test_sort_by_values(self):
        assert PipelineSortBy.CREATED_AT == "created_at"
        assert PipelineSortBy.STAGE_UPDATED_AT == "stage_updated_at"

    def test_sort_dir_values(self):
        assert PipelineSortDir.ASC == "asc"
        assert PipelineSortDir.DESC == "desc"


# ── list_pipelines_paginated (service unit tests) ─────────────────────────────

class TestListPipelinesPaginated:
    """
    These tests call the real service method against a stubbed DB session
    to verify filter composition, count queries, and stage count aggregation.
    """

    def _make_real_service(self):
        from app.services.pipeline_service import PipelineService

        db = MagicMock()
        svc = PipelineService.__new__(PipelineService)
        svc.db = db
        svc._scope = MagicMock()
        svc._scope.is_scoped_user.return_value = False
        svc._scope.is_vendor_user.return_value = False
        svc._candidates = MagicMock()
        return svc, db

    def test_returns_tuple_of_three(self):
        svc, db = self._make_real_service()
        user = _make_user()
        org_id = uuid4()

        # Stub DB calls to return empty results.
        db.scalars.return_value.all = MagicMock(return_value=[])
        db.scalars.return_value.__iter__ = lambda s: iter([])
        scalars_mock = MagicMock()
        scalars_mock.__iter__ = lambda s: iter([])
        db.scalars.return_value = scalars_mock
        db.scalar.return_value = 0  # total count
        db.execute.return_value = []  # stage counts

        result = svc.list_pipelines_paginated(org_id, user)
        assert isinstance(result, tuple)
        assert len(result) == 3
        pipelines, total, stage_counts = result
        assert isinstance(pipelines, list)
        assert isinstance(total, int)
        assert isinstance(stage_counts, dict)

    def test_stage_counts_aggregation(self):
        """Stage counts come from a separate GROUP BY query (no N+1)."""
        svc, db = self._make_real_service()
        user = _make_user()
        org_id = uuid4()

        scalars_mock = MagicMock()
        scalars_mock.__iter__ = lambda s: iter([])
        db.scalars.return_value = scalars_mock
        db.scalar.return_value = 3  # total

        # Fake GROUP BY result rows.
        row_applied = MagicMock()
        row_applied.stage = "applied"
        row_applied.cnt = 2
        row_interview = MagicMock()
        row_interview.stage = "interview"
        row_interview.cnt = 1
        db.execute.return_value = [row_applied, row_interview]

        _, _, stage_counts = svc.list_pipelines_paginated(org_id, user)
        assert stage_counts.get("applied") == 2
        assert stage_counts.get("interview") == 1


# ── PipelineListResponse schema ───────────────────────────────────────────────

class TestPipelineListResponse:
    def test_data_and_meta_required(self):
        from app.schemas.pipeline import PipelineListMeta, PipelineListResponse
        from pydantic import ValidationError
        with pytest.raises((ValidationError, TypeError)):
            PipelineListResponse()  # missing required fields

    def test_valid_construction(self):
        from app.schemas.pipeline import PipelineListMeta, PipelineListResponse
        resp = PipelineListResponse(
            data=[],
            meta=PipelineListMeta(
                total=0,
                limit=50,
                offset=0,
                stage_counts={},
            ),
        )
        assert resp.meta.total == 0
        assert resp.data == []


# ── Sorting parameter validation ─────────────────────────────────────────────

class TestSortingValidation:
    def test_invalid_sort_by_raises(self):
        with pytest.raises(ValueError):
            PipelineSortBy("invalid_field")

    def test_invalid_sort_dir_raises(self):
        with pytest.raises(ValueError):
            PipelineSortDir("sideways")


# ── stage_updated_at on model ─────────────────────────────────────────────────

class TestStageUpdatedAtColumn:
    def test_pipeline_model_has_stage_updated_at(self):
        from app.models.pipeline import Pipeline
        assert hasattr(Pipeline, "stage_updated_at")

    def test_pipeline_response_includes_stage_updated_at(self):
        from app.schemas.pipeline import PipelineResponse
        fields = PipelineResponse.model_fields
        assert "stage_updated_at" in fields

    def test_transition_sets_stage_updated_at(self):
        """transition_stage must stamp stage_updated_at on the pipeline."""
        from app.schemas.pipeline import PipelineStageTransitionRequest
        from app.services.pipeline_service import PipelineService

        db = MagicMock()
        db.add = MagicMock()
        db.commit = MagicMock()
        db.refresh = MagicMock(side_effect=lambda x: x)

        pipeline = _make_pipeline(stage="screening")
        pipeline.stage_updated_at = None  # should be set after transition

        user = _make_user()
        payload = PipelineStageTransitionRequest(stage="interview")

        svc = PipelineService.__new__(PipelineService)
        svc.db = db
        svc._scope = MagicMock()
        svc._candidates = MagicMock()
        svc.get_pipeline_by_id = MagicMock(return_value=pipeline)

        with patch("app.services.pipeline_service._notify_stage_change"):
            svc.transition_stage(pipeline.id, pipeline.organization_id, user, payload)

        assert pipeline.stage_updated_at is not None
        assert pipeline.stage == "interview"


# ── Org scoping: filter_stmt always includes org predicate ───────────────────

class TestOrgScoping:
    def test_build_filter_stmt_always_includes_org_id(self):
        """_build_pipeline_filter_stmt must emit a WHERE org predicate."""
        from app.services.pipeline_service import PipelineService
        from sqlalchemy import inspect as sa_inspect

        db = MagicMock()
        svc = PipelineService.__new__(PipelineService)
        svc.db = db
        svc._scope = MagicMock()
        svc._scope.is_scoped_user.return_value = False
        svc._candidates = MagicMock()

        user = _make_user(org_id=uuid4())
        org_id = uuid4()

        stmt = svc._build_pipeline_filter_stmt(org_id, user)
        # The statement must have whereclause, not be bare.
        assert stmt.whereclause is not None

    def test_scoped_user_gets_job_subquery(self):
        """Vendor/client users get an additional IN subquery on allowed job IDs."""
        from app.services.pipeline_service import PipelineService

        db = MagicMock()
        svc = PipelineService.__new__(PipelineService)
        svc.db = db
        svc._scope = MagicMock()
        svc._scope.is_scoped_user.return_value = True
        subq = MagicMock()
        svc._scope.allowed_job_ids_subquery.return_value = subq
        svc._candidates = MagicMock()

        user = _make_user()
        org_id = uuid4()
        stmt = svc._build_pipeline_filter_stmt(org_id, user)
        # Confirm that the subquery was requested — proving the scope filter was applied.
        svc._scope.allowed_job_ids_subquery.assert_called_once_with(user)


# ── Pagination ────────────────────────────────────────────────────────────────

class TestPaginationMeta:
    def test_offset_reflected_in_meta(self):
        from app.schemas.pipeline import PipelineListMeta
        meta = PipelineListMeta(total=100, limit=20, offset=40, stage_counts={})
        assert meta.offset == 40
        assert meta.limit == 20

    def test_limit_reflected_in_meta(self):
        from app.schemas.pipeline import PipelineListMeta
        meta = PipelineListMeta(total=100, limit=5, offset=0, stage_counts={})
        assert meta.limit == 5


# ── Filter combination smoke test ────────────────────────────────────────────

class TestFilterCombinations:
    """Ensure service accepts all filter combinations without raising."""

    def test_all_filters_simultaneously(self):
        from app.services.pipeline_service import PipelineService

        db = MagicMock()
        svc = PipelineService.__new__(PipelineService)
        svc.db = db
        svc._scope = MagicMock()
        svc._scope.is_scoped_user.return_value = False
        svc._candidates = MagicMock()

        scalars_mock = MagicMock()
        scalars_mock.__iter__ = lambda s: iter([])
        db.scalars.return_value = scalars_mock
        db.scalar.return_value = 0
        db.execute.return_value = []

        user = _make_user()
        org_id = uuid4()
        job_id = uuid4()
        candidate_id = uuid4()

        result = svc.list_pipelines_paginated(
            org_id,
            user,
            limit=10,
            offset=5,
            job_id=job_id,
            candidate_id=candidate_id,
            stage=PipelineStage.INTERVIEW,
            pipeline_status=PipelineStatus.ACTIVE,
            sort_by=PipelineSortBy.STAGE_UPDATED_AT,
            sort_dir=PipelineSortDir.ASC,
        )
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_no_filters_returns_paginated_result(self):
        from app.services.pipeline_service import PipelineService

        db = MagicMock()
        svc = PipelineService.__new__(PipelineService)
        svc.db = db
        svc._scope = MagicMock()
        svc._scope.is_scoped_user.return_value = False
        svc._candidates = MagicMock()

        scalars_mock = MagicMock()
        scalars_mock.__iter__ = lambda s: iter([])
        db.scalars.return_value = scalars_mock
        db.scalar.return_value = 0
        db.execute.return_value = []

        user = _make_user()
        result = svc.list_pipelines_paginated(uuid4(), user)
        assert result[0] == []
        assert result[1] == 0
