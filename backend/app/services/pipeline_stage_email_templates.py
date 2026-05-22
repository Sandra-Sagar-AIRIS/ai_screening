"""AIR-571 (COMM-003): Stage-based pipeline notification email templates."""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Canonical template keys (user-facing stage names).
NOTIFY_TEMPLATE_STAGES: frozenset[str] = frozenset(
    {"applied", "screening", "interview", "offered", "hired", "rejected"}
)

# Map pipeline DB stage values → template key.
_STAGE_ALIASES: dict[str, str] = {
    "ai_screening": "screening",
    "offer": "offered",
    "placed": "hired",
}

_STATIC_TEMPLATES: dict[str, dict[str, str]] = {
    "applied": {
        "subject": "Application update: Application received",
        "body": (
            "Hi {candidate_name},\n\n"
            "Thank you for applying to the {job_title} role. We have received your application "
            "and our team will review it shortly.\n\n"
            "Best regards,\n{company_name}"
        ),
    },
    "screening": {
        "subject": "Application update: Screening",
        "body": (
            "Hi {candidate_name},\n\n"
            "Your application for {job_title} has moved to the screening stage. "
            "Our recruiting team will be in touch if we need any additional information.\n\n"
            "Best regards,\n{company_name}"
        ),
    },
    "interview": {
        "subject": "Application update: Interview",
        "body": (
            "Hi {candidate_name},\n\n"
            "Great news — your application for {job_title} has progressed to the interview stage. "
            "We will contact you soon with scheduling details.\n\n"
            "Best regards,\n{company_name}"
        ),
    },
    "offered": {
        "subject": "Application update: Offer",
        "body": (
            "Hi {candidate_name},\n\n"
            "We are pleased to let you know that you have received an offer for the {job_title} role. "
            "A member of our team will follow up with the offer details.\n\n"
            "Best regards,\n{company_name}"
        ),
    },
    "hired": {
        "subject": "Application update: Hired",
        "body": (
            "Hi {candidate_name},\n\n"
            "Congratulations! Your application for {job_title} has been marked as hired. "
            "Welcome aboard — we look forward to working with you.\n\n"
            "Best regards,\n{company_name}"
        ),
    },
    "rejected": {
        "subject": "Application update: Decision",
        "body": (
            "Hi {candidate_name},\n\n"
            "Thank you for your interest in the {job_title} role. After careful consideration, "
            "we will not be moving forward with your application at this time. "
            "We appreciate the time you invested and wish you the best in your search.\n\n"
            "Best regards,\n{company_name}"
        ),
    },
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MAX_BODY_CHARS = 8000


@dataclass(frozen=True, slots=True)
class PipelineStageEmailTemplate:
    stage_key: str
    subject: str
    body: str
    groq_enhanced: bool = False


def normalize_stage_for_pipeline_email(stage: str) -> str | None:
    """Map a pipeline stage value to a template key, or None if we should not notify."""
    key = _STAGE_ALIASES.get(stage.strip().lower(), stage.strip().lower())
    if key not in NOTIFY_TEMPLATE_STAGES:
        return None
    return key


def _safe_format(template: str, values: dict[str, str]) -> str:
    try:
        return template.format(**values)
    except KeyError:
        logger.warning("pipeline_stage_email_templates.missing_placeholder", exc_info=True)
        return template


def _sanitize_email_body(text: str) -> str:
    cleaned = _HTML_TAG_RE.sub("", text)
    cleaned = html.unescape(cleaned)
    cleaned = _CONTROL_CHAR_RE.sub("", cleaned).strip()
    if len(cleaned) > _MAX_BODY_CHARS:
        cleaned = cleaned[:_MAX_BODY_CHARS]
    return cleaned


def _resolve_groq_api_key() -> str | None:
    """Use GROQ_API_KEY or GROQ_API_KEY_ATS (same Groq account, different env names)."""
    settings = get_settings()
    for candidate in (settings.groq_api_key, settings.groq_ats_api_key):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return None


def _maybe_enhance_body_with_groq(*, base_body: str, context: dict[str, str]) -> str | None:
    settings = get_settings()
    api_key = _resolve_groq_api_key()
    if not api_key:
        logger.debug(
            "pipeline_stage_email_templates.groq_skipped reason=no_api_key "
            "(set GROQ_API_KEY or GROQ_API_KEY_ATS in backend .env)"
        )
        return None

    stage_label = context.get("stage_label") or context.get("new_stage") or "update"
    previous_stage = context.get("previous_stage") or ""
    transition_note = (
        f"Pipeline transition: {previous_stage} → {context.get('new_stage', stage_label)}"
        if previous_stage
        else f"Pipeline stage: {stage_label}"
    )
    reason = (context.get("reason") or "").strip()
    reason_line = f"Recruiter note (include sensitively if relevant): {reason}\n" if reason else ""

    prompt = (
        "You are writing a transactional recruiting email to a job candidate. "
        "Rewrite the draft body below to be professional, warm, and concise (under 180 words). "
        "Keep all factual details (name, role, stage, company). Do not invent dates, salaries, or promises. "
        "Return ONLY the email body as plain text — no subject, no markdown fences, no JSON.\n\n"
        f"{transition_note}\n"
        f"Candidate: {context.get('candidate_name', '')}\n"
        f"Role: {context.get('job_title', '')}\n"
        f"Company: {context.get('company_name', '')}\n"
        f"{reason_line}\n"
        f"Draft body:\n{base_body}"
    )

    timeout = max(1.0, float(settings.groq_ats_timeout_seconds))
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{settings.groq_ats_api_base.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.groq_ats_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                    "max_tokens": 600,
                },
            )
            response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        sanitized = _sanitize_email_body(content.replace("```", "").strip())
        if sanitized:
            logger.info(
                "pipeline_stage_email_templates.groq_enhanced stage=%s model=%s",
                stage_label,
                settings.groq_ats_model,
            )
        return sanitized or None
    except Exception:
        logger.warning(
            "pipeline_stage_email_templates.groq_failed stage=%s — using static fallback",
            stage_label,
            exc_info=True,
        )
        return None


def get_pipeline_stage_email_template(
    stage: str,
    *,
    context: dict[str, Any] | None = None,
) -> PipelineStageEmailTemplate | None:
    """
    Return subject/body for a pipeline stage notification email.

    Uses static COMM-003 fallbacks, then enhances the body via Groq when GROQ_API_KEY or
    GROQ_API_KEY_ATS is configured (subject stays static; Groq failure falls back safely).
    """
    stage_key = normalize_stage_for_pipeline_email(stage)
    if stage_key is None:
        return None

    static = _STATIC_TEMPLATES[stage_key]
    values: dict[str, str] = {
        "candidate_name": "there",
        "job_title": "the role",
        "company_name": "Our team",
        "previous_stage": "",
        "new_stage": stage,
        "stage_label": stage_key.replace("_", " ").title(),
    }
    if context:
        for key, raw in context.items():
            if raw is None:
                continue
            values[key] = str(raw).strip() or values.get(key, "")

    base_body = _safe_format(static["body"], values)
    enhanced = _maybe_enhance_body_with_groq(base_body=base_body, context=values)
    body = _sanitize_email_body(enhanced or base_body)
    subject = _safe_format(static["subject"], values)

    return PipelineStageEmailTemplate(
        stage_key=stage_key,
        subject=subject,
        body=body,
        groq_enhanced=enhanced is not None,
    )
