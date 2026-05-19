"""Unit tests for fast candidate text search helpers."""

from __future__ import annotations

from app.candidate_management.search import (
    build_candidate_text_search_filter,
    escape_ilike_pattern,
    normalize_search_query,
)


def test_normalize_search_query_trims_and_collapses_whitespace() -> None:
    assert normalize_search_query("  aravind   kumar  ") == "aravind kumar"
    assert normalize_search_query("") is None
    assert normalize_search_query(None) is None


def test_escape_ilike_pattern_escapes_wildcards() -> None:
    assert escape_ilike_pattern("50%_done") == "50\\%\\_done"


def test_build_candidate_text_search_filter_returns_none_for_blank() -> None:
    assert build_candidate_text_search_filter("") is None
    assert build_candidate_text_search_filter("   ") is None


def test_build_candidate_text_search_filter_builds_or_clause() -> None:
    clause = build_candidate_text_search_filter("devops")
    assert clause is not None
    compiled = str(clause.compile(compile_kwargs={"literal_binds": True}))
    assert "full_name" in compiled.lower()
    assert "devops" in compiled.lower()
