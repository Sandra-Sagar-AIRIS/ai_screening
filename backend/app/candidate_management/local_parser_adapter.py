"""Adapter that implements `AIServicePort.parse_resume` using the local
deterministic parser + ATS extraction service.

Design:
- This is the default path for resume parsing now.
- It composes `resume_parser.parse_resume_file` and `ATSExtractionService` so
  the rest of `CandidateManagementService` (which depends only on the port)
  does not need to know whether the parser is local or remote.
- `LocalParserWithAIFallback` chains a local parser with an optional AI
  fallback (HttpAIService). If the local parse produces low-confidence or
  empty results AND an AI service is configured, it tries the AI parser.
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidate_management.schemas import CandidateSkillInput, ResumeParseResult
from app.models.job_skill import JobSkill
from app.services.ats_extraction_service import ATSExtractionService
from app.services.resume_parser import ParsedResume, ResumeParseError, parse_resume_file

logger = logging.getLogger(__name__)


# Local fallback confidence threshold below which we will try the AI fallback
# (if configured). Tunable via env so prod can be more aggressive.
_LOCAL_PARSER_VERSION = "local-ats-v1"
_FALLBACK_THRESHOLD = float(os.getenv("ATS_LOCAL_FALLBACK_THRESHOLD", "0.35"))


class LocalResumeParser:
    """Parses a resume file from disk and returns a `ResumeParseResult`."""

    def __init__(self, *, db: Session | None = None) -> None:
        # `db` is optional so tests can run this without a session. When it's
        # supplied we union JobSkill rows into the extractor's known-skills
        # set so the dictionary stays in sync with what jobs actually need.
        self.db = db

    # AIServicePort
    def parse_resume(self, *, resume_s3_key: str) -> ResumeParseResult:
        file_path = _resolve_local_file(resume_s3_key)
        try:
            parsed = parse_resume_file(file_path)
        except ResumeParseError as exc:
            logger.warning("Local parser failed for %s: %s", resume_s3_key, exc)
            return _empty_result(reason=str(exc))

        extractor = ATSExtractionService(known_skills=self._known_skills())
        profile = extractor.extract(parsed)
        contact = _extract_contact(parsed.text)
        name_parts = _extract_name(parsed.text)

        parsed_resume_data: dict[str, Any] = {
            "full_name": name_parts.get("full_name"),
            "first_name": name_parts.get("first_name"),
            "last_name": name_parts.get("last_name"),
            "email": contact.get("email"),
            "phone": contact.get("phone"),
            "location": contact.get("location"),
            "headline": _first_non_empty(profile.previous_titles),
            "summary": (parsed.sections.get("summary") or parsed.text[:1000]) or None,
            "years_experience": (
                int(profile.years_of_experience) if profile.years_of_experience is not None else None
            ),
            "education": profile.education,
            "certifications": profile.certifications,
            "previous_titles": profile.previous_titles,
            "normalized_keywords": profile.normalized_keywords,
            "parser": parsed.parser,
        }

        return ResumeParseResult(
            parsed_resume_data=parsed_resume_data,
            parse_confidence=profile.confidence,
            ai_parse_version=_LOCAL_PARSER_VERSION,
            extracted_skills=[
                CandidateSkillInput(name=skill, source="local-extractor")
                for skill in profile.skills
            ],
            years_of_experience=profile.years_of_experience,
            education=profile.education,
            certifications=profile.certifications,
            previous_titles=profile.previous_titles,
            normalized_keywords=profile.normalized_keywords,
        )

    # Pass-through stub: smart_search isn't part of local parsing. Caller should
    # use a different adapter for AI search. We keep this method so this class
    # can be dropped in wherever AIServicePort is expected.
    def smart_search(self, *, query: str, org_id: UUID, workspace_id: UUID, limit: int) -> list[UUID]:  # noqa: ARG002
        return []

    # ------------------------------------------------------------------
    def _known_skills(self) -> list[str]:
        if self.db is None:
            return []
        try:
            rows = self.db.scalars(select(JobSkill.skill)).all()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load JobSkill rows for skill catalogue: %s", exc)
            return []
        return [str(s) for s in rows if s]


class LocalParserWithAIFallback:
    """Local-first parser with an optional AI fallback.

    If the local extractor produced almost nothing (low confidence) AND a
    `fallback_service` is provided, we try the fallback. The local result is
    still returned when the fallback also fails.
    """

    def __init__(self, *, local: LocalResumeParser, fallback: Any | None = None) -> None:
        self.local = local
        self.fallback = fallback

    def parse_resume(self, *, resume_s3_key: str) -> ResumeParseResult:
        local_result = self.local.parse_resume(resume_s3_key=resume_s3_key)
        if not _is_local_weak(local_result):
            return local_result

        if self.fallback is None:
            return local_result

        try:
            ai_result = self.fallback.parse_resume(resume_s3_key=resume_s3_key)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "AI fallback parser failed; keeping local result. resume_s3_key=%s err=%s",
                resume_s3_key,
                exc,
            )
            return local_result

        # Merge: AI populates demographics; local keeps the structured ATS fields.
        merged_resume_data = {**(ai_result.parsed_resume_data or {}), **local_result.parsed_resume_data}
        merged_skills = {s.name.lower(): s for s in local_result.extracted_skills}
        for skill in ai_result.extracted_skills:
            merged_skills.setdefault(skill.name.lower(), skill)
        return ResumeParseResult(
            parsed_resume_data=merged_resume_data,
            parse_confidence=max(
                local_result.parse_confidence or 0.0,
                ai_result.parse_confidence or 0.0,
            ),
            ai_parse_version=f"{_LOCAL_PARSER_VERSION}+{ai_result.ai_parse_version or 'ai'}",
            extracted_skills=list(merged_skills.values()),
            years_of_experience=local_result.years_of_experience,
            education=local_result.education,
            certifications=local_result.certifications,
            previous_titles=local_result.previous_titles,
            normalized_keywords=local_result.normalized_keywords,
        )

    def smart_search(self, *, query: str, org_id: UUID, workspace_id: UUID, limit: int) -> list[UUID]:
        if self.fallback is not None and hasattr(self.fallback, "smart_search"):
            try:
                return self.fallback.smart_search(query=query, org_id=org_id, workspace_id=workspace_id, limit=limit)
            except Exception:  # noqa: BLE001
                logger.warning("AI smart_search failed; returning empty result.")
        return []


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _resolve_local_file(resume_s3_key: str) -> Path:
    """Map a logical resume key to the on-disk file the parser opens.

    Mirrors the convention used by `HttpAIService._local_parse_payload` so
    uploads written via the existing API are readable by this adapter.
    """
    storage_root = Path(os.getenv("CANDIDATE_RESUME_UPLOAD_DIR", "tmp/candidate-resumes"))
    return storage_root / resume_s3_key.replace("/", "_")


def _empty_result(*, reason: str) -> ResumeParseResult:
    return ResumeParseResult(
        parsed_resume_data={"parse_error": reason},
        parse_confidence=0.0,
        ai_parse_version=_LOCAL_PARSER_VERSION,
        extracted_skills=[],
        years_of_experience=None,
        education=[],
        certifications=[],
        previous_titles=[],
        normalized_keywords=[],
    )


def _is_local_weak(result: ResumeParseResult) -> bool:
    if (result.parse_confidence or 0.0) < _FALLBACK_THRESHOLD:
        return True
    if not result.extracted_skills and not result.years_of_experience:
        return True
    return False


_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"\+?\d[\d\-\s().]{7,}\d")


def _extract_contact(text: str) -> dict[str, str | None]:
    email = _EMAIL_RE.search(text)
    phone = _PHONE_RE.search(text)
    location = _extract_location(text)
    return {
        "email": email.group(0).lower() if email else None,
        "phone": phone.group(0).strip() if phone else None,
        "location": location,
    }


def _extract_name(text: str) -> dict[str, str | None]:
    # Heuristic: first non-empty line that looks like "Firstname Lastname".
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped) > 80:
            continue
        if "@" in stripped or any(ch.isdigit() for ch in stripped):
            continue
        words = stripped.split()
        if 2 <= len(words) <= 4 and all(w[:1].isalpha() for w in words):
            return {
                "full_name": stripped,
                "first_name": words[0],
                "last_name": " ".join(words[1:]),
            }
    return {"full_name": None, "first_name": None, "last_name": None}


_KNOWN_CITIES = (
    "bangalore", "bengaluru", "chennai", "hyderabad", "mumbai", "delhi",
    "pune", "kolkata", "ahmedabad", "noida", "gurugram", "gurgaon",
    "san francisco", "new york", "seattle", "boston", "austin",
    "london", "berlin", "paris", "singapore", "toronto", "sydney",
)


def _extract_location(text: str) -> str | None:
    text_l = text.lower()
    for city in _KNOWN_CITIES:
        if city in text_l:
            return city.title()
    return None


def _first_non_empty(items: list[str]) -> str | None:
    for item in items:
        if item and item.strip():
            return item.strip()
    return None
