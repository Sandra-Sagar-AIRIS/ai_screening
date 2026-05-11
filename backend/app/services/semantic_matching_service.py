"""Semantic ATS enrichment via Grok — structured JSON only.

Builds a minimal structured payload (no raw PDF). On any failure returns None
so deterministic ATS remains authoritative.
"""
from __future__ import annotations

import json
import logging
import re
import time
from hashlib import sha256
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.services.ai_ats_service import GrokAtsClient, GrokUnavailableError, GroqAtsClient

logger = logging.getLogger(__name__)
_SEM_CACHE: dict[str, tuple[float, "SemanticEnrichmentResult"]] = {}
_SEM_CACHE_TTL_SECONDS = 900

_SYSTEM = """You are an expert technical recruiter assistant. Compare candidate profile data to job requirements.
Return ONLY valid JSON matching this exact schema (no markdown, no prose outside JSON):
{
  "semantic_match_score": <integer 0-100>,
  "semantic_skill_matches": [<string>, ...],
  "transferable_skills": [<string>, ...],
  "inferred_strengths": [<string>, ...],
  "inferred_gaps": [<string>, ...],
  "recruiter_summary": <string, 2-4 sentences, factual>,
  "confidence_reasoning": <string, 1-2 sentences on why this semantic score is justified>
}
Rules:
- semantic_match_score reflects holistic semantic fit (skills ecosystems, seniority, role context), not literal string overlap.
- Recognize related tech (e.g. NestJS with Node.js, Kafka with distributed systems, Terraform with IaC).
- Be conservative: do not invent credentials or employers not implied by the data.
- Keep lists short (max 8 items each). Use concise phrases.
"""


class SemanticAtsPayload(BaseModel):
    semantic_match_score: int = Field(ge=0, le=100)
    semantic_skill_matches: list[str] = Field(default_factory=list)
    transferable_skills: list[str] = Field(default_factory=list)
    inferred_strengths: list[str] = Field(default_factory=list)
    inferred_gaps: list[str] = Field(default_factory=list)
    recruiter_summary: str = ""
    confidence_reasoning: str = ""

    @field_validator(
        "semantic_skill_matches",
        "transferable_skills",
        "inferred_strengths",
        "inferred_gaps",
        mode="before",
    )
    @classmethod
    def _coerce_str_list(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()][:12]
        return []


@dataclass(slots=True)
class SemanticEnrichmentResult:
    payload: SemanticAtsPayload


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError("no json object in grok response")
    return json.loads(m.group(0))


def build_condensed_candidate_job_payload(
    *,
    candidate_skills: list[str],
    candidate_titles: list[str],
    years_experience: float | None,
    education: list[str],
    certifications: list[str],
    experience_summary: str | None,
    job_title: str | None,
    job_summary: str | None,
    job_required_skills: list[str],
    job_preferred_skills: list[str],
    deterministic_score: int,
    deterministic_matched: list[str],
    deterministic_missing: list[str],
) -> dict[str, Any]:
    """Small dict for Grok user message (token-efficient)."""

    def _clip(s: str | None, n: int) -> str:
        if not s:
            return ""
        s = s.strip()
        return s if len(s) <= n else s[: n - 1] + "…"

    return {
        "candidate_skills": candidate_skills[:40],
        "candidate_titles": candidate_titles[:8],
        "years_experience": years_experience,
        "education": education[:6],
        "certifications": certifications[:10],
        "experience_summary": _clip(experience_summary, 1200),
        "job_title": job_title or "",
        "job_summary": _clip(job_summary, 1200),
        "job_required_skills": job_required_skills[:40],
        "job_preferred_skills": job_preferred_skills[:40],
        "deterministic_ats": {
            "score": deterministic_score,
            "matched_skills": deterministic_matched[:30],
            "missing_skills": deterministic_missing[:30],
        },
    }


class SemanticMatchingService:
    def enrich_pair(self, condensed: dict[str, Any]) -> SemanticEnrichmentResult | None:
        # Prefer Groq semantic ATS when configured (it uses a separate key),
        # otherwise fall back to xAI Grok.
        client: Any = GroqAtsClient()
        provider = "groq"
        if not client.is_configured():
            client = GrokAtsClient()
            provider = "xai"
        if not client.is_configured():
            logger.info("semantic_ats_skip semantic_provider_not_configured")
            return None

        user = json.dumps(condensed, ensure_ascii=False, separators=(",", ":"))
        cache_key = sha256(user.encode("utf-8")).hexdigest()
        now = time.monotonic()
        cached = _SEM_CACHE.get(cache_key)
        if cached and (now - cached[0]) < _SEM_CACHE_TTL_SECONDS:
            logger.info(
                "ats.semantic.cache_hit",
                extra={"ats_phase": "semantic_enrichment", "cache_ttl_seconds": _SEM_CACHE_TTL_SECONDS},
            )
            return cached[1]
        try:
            logger.info(
                "ats.semantic.started",
                extra={
                    "ats_phase": "semantic_enrichment",
                    "provider": provider,
                    "model": getattr(client, "_model", None),
                    "payload_chars": len(user),
                },
            )
            raw = client.chat_json_system_user(system=_SYSTEM, user=user)
            data = _extract_json_object(raw)
            payload = SemanticAtsPayload.model_validate(data)
            logger.info(
                "ats.semantic.completed",
                extra={
                    "ats_phase": "semantic_enrichment",
                    "semantic_match_score": payload.semantic_match_score,
                    "semantic_skill_matches_count": len(payload.semantic_skill_matches or []),
                },
            )
            result = SemanticEnrichmentResult(payload=payload)
            _SEM_CACHE[cache_key] = (time.monotonic(), result)
            return result
        except (GrokUnavailableError, json.JSONDecodeError, ValueError) as e:
            logger.warning(
                "ats.semantic.failed",
                extra={
                    "ats_phase": "semantic_enrichment",
                    "exception_type": type(e).__name__,
                    "error": str(e)[:500],
                },
                exc_info=False,
            )
            return None
        except Exception:
            logger.exception(
                "ats.semantic.failed",
                extra={
                    "ats_phase": "semantic_enrichment",
                    "exception_type": "unexpected",
                },
            )
            return None


def hybrid_match_score(deterministic: int, semantic: int | None) -> int:
    """70% deterministic + 30% semantic; if no semantic, deterministic only."""
    d = max(0, min(100, int(deterministic)))
    if semantic is None:
        return d
    s = max(0, min(100, int(semantic)))
    return int(round(0.7 * d + 0.3 * s))
