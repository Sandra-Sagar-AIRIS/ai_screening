"""Normalize job requirements before persistence.

Why this is a separate module:
- Skill name normalization (case, aliasing, dedup) is logic that is identical
  for create and update paths. Centralizing it here keeps `JobService` focused
  on transactions and audit, and lets the matching service share the same
  alias map without circular imports.

Scope:
- We do not attempt full JD-to-fields parsing (that already exists via the
  `/jobs/parse-jd` Groq path). We just clean and structure the skill lists
  the caller hands in, and return a `NormalizedJobRequirements` value that
  `JobService` and the ATS matching engine can both consume.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
import re


# Curated skill alias map. Resume text and JD text often disagree on spelling
# ("k8s" vs "kubernetes", "node" vs "node.js"). We normalize to a canonical
# form on both sides before comparing.
SKILL_ALIASES: dict[str, str] = {
    "js": "javascript",
    "ts": "typescript",
    "node": "node.js",
    "nodejs": "node.js",
    "k8s": "kubernetes",
    "kube": "kubernetes",
    "postgres": "postgresql",
    "psql": "postgresql",
    "py": "python",
    "golang": "go",
    "react.js": "react",
    "reactjs": "react",
    "vuejs": "vue",
    "vue.js": "vue",
    "nextjs": "next.js",
    "next": "next.js",
    "tf": "terraform",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "ci/cd": "ci-cd",
    "ci_cd": "ci-cd",
    "gcp": "google cloud",
    "aws s3": "aws",
    # Resume / free-text variants (not always used in JD pickers)
    "rest apis": "rest",
    "restful": "rest",
    "rest api": "rest",
    "mongo db": "mongodb",
    "mongo": "mongodb",
    "ms sql": "sql server",
    "mssql": "sql server",
    "ms-sql": "sql server",
    "open telemetry": "opentelemetry",
    "otel": "opentelemetry",
}


@dataclass(slots=True)
class NormalizedJobRequirements:
    """Structured, ATS-ready job requirements.

    `required_skills_raw` keeps the original casing so the UI can keep showing
    "AWS" (not "aws"). `required_skills_normalized` is what the matching
    engine compares against the candidate's normalized keywords.
    """

    required_skills_raw: list[str] = field(default_factory=list)
    preferred_skills_raw: list[str] = field(default_factory=list)
    required_skills_normalized: list[str] = field(default_factory=list)
    preferred_skills_normalized: list[str] = field(default_factory=list)
    key_responsibilities: list[str] = field(default_factory=list)


class JDNormalizationService:
    """Stateless normalizer. Safe to instantiate per request."""

    def normalize(
        self,
        *,
        required_skills: Iterable[str] | None,
        preferred_skills: Iterable[str] | None = None,
        key_responsibilities: Iterable[str] | None = None,
    ) -> NormalizedJobRequirements:
        required_raw, required_norm = self._clean_skills(required_skills)
        preferred_raw, preferred_norm = self._clean_skills(preferred_skills)

        # If a skill is both required and preferred, required wins (the
        # matching engine penalizes missing required harder).
        required_norm_set = set(required_norm)
        preferred_raw = [
            raw for raw, norm in zip(preferred_raw, preferred_norm) if norm not in required_norm_set
        ]
        preferred_norm = [norm for norm in preferred_norm if norm not in required_norm_set]

        responsibilities = [str(r).strip() for r in (key_responsibilities or []) if r and str(r).strip()]

        return NormalizedJobRequirements(
            required_skills_raw=required_raw,
            preferred_skills_raw=preferred_raw,
            required_skills_normalized=required_norm,
            preferred_skills_normalized=preferred_norm,
            key_responsibilities=responsibilities,
        )

    @staticmethod
    def normalize_skill(value: str) -> str:
        """Lowercase + alias map a single skill string. Public so the matching
        service can reuse the exact same canonicalization."""
        cleaned = value.strip().lower()
        if not cleaned:
            return ""
        # Strip parenthetical clarifications (e.g. "nosql databases (mongodb / redis)").
        cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", cleaned)
        cleaned = re.sub(r"[/|,;]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # Alias map runs after cleanup so "K8s " maps to "kubernetes".
        return SKILL_ALIASES.get(cleaned, cleaned)

    def _clean_skills(self, items: Iterable[str] | None) -> tuple[list[str], list[str]]:
        if not items:
            return [], []
        seen_norm: set[str] = set()
        raw_out: list[str] = []
        norm_out: list[str] = []
        for item in items:
            if item is None:
                continue
            raw = str(item).strip()
            if not raw:
                continue
            normalized = self.normalize_skill(raw)
            if not normalized or normalized in seen_norm:
                continue
            seen_norm.add(normalized)
            raw_out.append(raw)
            norm_out.append(normalized)
        return raw_out, norm_out
