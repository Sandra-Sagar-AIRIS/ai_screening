"""AI Query Generation Engine.

Derives structured SourcingQuery from a job description using Groq LLM.
Falls back to keyword extraction via JDNormalizationService if the LLM call fails.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.sourcing.providers.base import SourcingQuery

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are a technical recruiter assistant.
Extract structured search parameters from the job description provided.
Return ONLY valid JSON (no markdown, no prose) matching this exact schema:
{
  "title": "<primary job title, concise>",
  "skills": ["<skill1>", "<skill2>", ...],
  "keywords": ["<keyword1>", ...],
  "location": "<city/country or null>",
  "experience_min": <integer years or null>,
  "experience_max": <integer years or null>
}
Rules:
- skills: list 5-10 core technical skills (tools, languages, frameworks)
- keywords: list 3-5 additional domain keywords (not already in skills)
- Keep title concise (2-4 words)
- experience_min/max: derive from "X+ years" or "X-Y years" phrasing; null if not stated
"""


class SourcingQueryGenerator:
    """Generates SourcingQuery from JD text via Groq LLM with fallback."""

    def generate(self, jd_text: str, overrides: dict[str, Any] | None = None) -> SourcingQuery:
        """Generate a SourcingQuery from *jd_text*.

        Tries Groq first; falls back to JDNormalizationService keyword extraction on error.
        *overrides* can supply title/location/skills to override the LLM result.
        """
        overrides = overrides or {}
        query = self._generate_via_llm(jd_text) or self._generate_via_fallback(jd_text)

        # Apply caller-supplied overrides
        if "title" in overrides and overrides["title"]:
            query.title = str(overrides["title"])
        if "location" in overrides and overrides["location"]:
            query.location = str(overrides["location"])
        if "skills" in overrides and overrides["skills"]:
            query.skills = list(overrides["skills"])
        if "experience_min" in overrides:
            query.experience_min = overrides["experience_min"]
        if "experience_max" in overrides:
            query.experience_max = overrides["experience_max"]

        return query

    # ── Private ────────────────────────────────────────────────────────────────

    def _generate_via_llm(self, jd_text: str) -> SourcingQuery | None:
        try:
            from app.services.ai_ats_service import GroqAtsClient, GrokAtsClient

            # Prefer Groq (cheaper/faster), fall back to Grok (xAI)
            client: GroqAtsClient | GrokAtsClient = GroqAtsClient()
            if not client.is_configured():
                client = GrokAtsClient()
            if not client.is_configured():
                logger.info("sourcing.query_generator.no_llm_configured")
                return None

            raw = client.chat_json_system_user(
                system=_SYSTEM_PROMPT,
                user=jd_text[:4000],
            )
            return self._parse_llm_response(raw)
        except Exception:
            logger.warning("sourcing.query_generator.llm_failed", exc_info=True)
            return None

    def _parse_llm_response(self, raw: str) -> SourcingQuery:
        text = raw.strip()
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            raise ValueError("no JSON object in LLM response")
        data: dict[str, Any] = json.loads(m.group(0))
        return SourcingQuery(
            title=str(data.get("title") or ""),
            skills=[str(s).strip() for s in (data.get("skills") or []) if s][:15],
            keywords=[str(k).strip() for k in (data.get("keywords") or []) if k][:10],
            location=str(data["location"]) if data.get("location") else None,
            experience_min=int(data["experience_min"]) if data.get("experience_min") is not None else None,
            experience_max=int(data["experience_max"]) if data.get("experience_max") is not None else None,
        )

    def _generate_via_fallback(self, jd_text: str) -> SourcingQuery:
        """Keyword extraction fallback — no LLM required."""
        logger.info("sourcing.query_generator.using_fallback")
        # Extract capitalised words as candidate skills heuristic
        import re as _re
        skills = list(dict.fromkeys(
            w.strip(".,;:()") for w in jd_text.split()
            if len(w) > 3 and w[0].isupper() and w.isalpha()
        ))[:10]

        # Simple heuristic title extraction: first line that looks like a job title
        title = ""
        for line in jd_text.splitlines():
            line = line.strip()
            if 3 <= len(line.split()) <= 6 and not line.endswith(":"):
                title = line
                break

        # Experience extraction via regex
        exp_min = exp_max = None
        m = re.search(r"(\d+)\s*[–\-to]+\s*(\d+)\s*years?", jd_text, re.IGNORECASE)
        if m:
            exp_min, exp_max = int(m.group(1)), int(m.group(2))
        else:
            m2 = re.search(r"(\d+)\+?\s*years?", jd_text, re.IGNORECASE)
            if m2:
                exp_min = int(m2.group(1))

        return SourcingQuery(
            title=title,
            skills=skills,
            keywords=[],
            location=None,
            experience_min=exp_min,
            experience_max=exp_max,
        )
