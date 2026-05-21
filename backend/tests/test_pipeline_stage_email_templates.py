"""AIR-571: Pipeline stage email template helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.pipeline_stage_email_templates import (
    get_pipeline_stage_email_template,
    normalize_stage_for_pipeline_email,
)


def test_normalize_stage_aliases():
    assert normalize_stage_for_pipeline_email("ai_screening") == "screening"
    assert normalize_stage_for_pipeline_email("offer") == "offered"
    assert normalize_stage_for_pipeline_email("placed") == "hired"
    assert normalize_stage_for_pipeline_email("interview") == "interview"
    assert normalize_stage_for_pipeline_email("unknown") is None


def test_static_template_without_groq():
    with patch("app.services.pipeline_stage_email_templates.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = None
        tpl = get_pipeline_stage_email_template(
            "screening",
            context={"candidate_name": "Alex", "job_title": "Engineer"},
        )
    assert tpl is not None
    assert tpl.stage_key == "screening"
    assert "Alex" in tpl.body
    assert "Engineer" in tpl.body
    assert tpl.subject.startswith("Application update:")
    assert tpl.groq_enhanced is False


def test_groq_failure_falls_back_to_static():
    with patch("app.services.pipeline_stage_email_templates.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = "test-key"
        mock_settings.return_value.groq_ats_api_key = None
        mock_settings.return_value.groq_ats_api_base = "https://api.groq.com/openai/v1"
        mock_settings.return_value.groq_ats_model = "llama-3.3-70b-versatile"
        mock_settings.return_value.groq_ats_timeout_seconds = 5.0
        with patch(
            "app.services.pipeline_stage_email_templates.httpx.Client",
            side_effect=RuntimeError("network down"),
        ):
            tpl = get_pipeline_stage_email_template("rejected", context={"candidate_name": "Sam"})
    assert tpl is not None
    assert tpl.groq_enhanced is False
    assert "Sam" in tpl.body


def test_groq_uses_ats_api_key_when_primary_missing():
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hi Sam,\n\nYour screening update.\n\nBest,\nTeam"}}]
    }
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.services.pipeline_stage_email_templates.get_settings") as mock_settings:
        mock_settings.return_value.groq_api_key = None
        mock_settings.return_value.groq_ats_api_key = "ats-key"
        mock_settings.return_value.groq_ats_api_base = "https://api.groq.com/openai/v1"
        mock_settings.return_value.groq_ats_model = "llama-3.3-70b-versatile"
        mock_settings.return_value.groq_ats_timeout_seconds = 5.0
        with patch(
            "app.services.pipeline_stage_email_templates.httpx.Client",
            return_value=mock_client,
        ):
            tpl = get_pipeline_stage_email_template(
                "screening",
                context={"candidate_name": "Sam", "job_title": "Engineer"},
            )
    assert tpl is not None
    assert tpl.groq_enhanced is True
    assert "screening" in tpl.body.lower() or "Sam" in tpl.body
