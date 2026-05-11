"""Optional Grok-backed resume intelligence enrichment.

Runs **after** deterministic local extraction. Merges structured JSON into
`parsed_resume_data` when `RESUME_GROK_INTELLIGENCE=1` and GROK_API_KEY is set.
Does not block if Grok fails — caller keeps local results.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.ai_ats_service import GrokAtsClient, GrokUnavailableError

logger = logging.getLogger(__name__)


class ResumeIntelligencePayload(BaseModel):
    """Validated JSON-only Grok output."""

    model_config = ConfigDict(extra="ignore")

    normalized_skills: list[str] = Field(default_factory=list)
    inferred_skills: list[str] = Field(default_factory=list)
    titles: list[str] = Field(default_factory=list)
    seniority: str | None = None
    cloud_platforms: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    leadership_signals: list[str] = Field(default_factory=list)
    recruiter_summary: str | None = None


_SYSTEM_PROMPT = """You are a resume parsing assistant for recruiters.
Return ONLY valid JSON matching this schema (no markdown fences):
{
  "normalized_skills": string[],
  "inferred_skills": string[],
  "titles": string[],
  "seniority": string or null (e.g. junior, mid, senior, lead, principal),
  "cloud_platforms": string[],
  "frameworks": string[],
  "databases": string[],
  "certifications": string[],
  "leadership_signals": string[],
  "recruiter_summary": string or null (2-4 sentences, factual, no PII beyond role fit)
}
Rules:
- normalized_skills: canonical tech names lower-case (react, node.js, postgresql).
- inferred_skills: reasonable implicits (e.g. rest apis if full-stack web is clear) — be conservative.
- Do not invent employers or degrees not supported by the text.
- Keep arrays short (max 25 items each for skills-like fields)."""


def _parse_json_object(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    m = re.search(r"\{[\s\S]*\}\s*$", raw)
    if m:
        raw = m.group(0)
    return json.loads(raw)


def enrich_resume_with_grok(
    *,
    resume_excerpt: str,
    local_skills: list[str],
) -> ResumeIntelligencePayload | None:
    """Call Grok once; return validated payload or None on any failure."""
    client = GrokAtsClient()
    if not client.is_configured():
        return None

    excerpt = (resume_excerpt or "").strip()
    if len(excerpt) > 12000:
        excerpt = excerpt[:12000] + "\n…"

    user = json.dumps(
        {
            "local_skills_already_found": local_skills[:80],
            "resume_text": excerpt,
        },
        ensure_ascii=True,
    )

    try:
        content = client.chat_json_system_user(system=_SYSTEM_PROMPT, user=user, temperature=0.1)
        data = _parse_json_object(content)
        return ResumeIntelligencePayload.model_validate(data)
    except (GrokUnavailableError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("resume_intelligence_grok_skip: %s", exc)
        return None
    except Exception:
        logger.exception("resume_intelligence_grok_failed")
        return None
