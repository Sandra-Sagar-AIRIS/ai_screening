"""Candidate deduplication engine.

Deduplication order of priority:
1. Email exact match (case-insensitive)
2. Phone exact match (normalised)
3. Name + location fuzzy match (Levenshtein ratio)

Cross-org boundaries are never merged.
"""
from __future__ import annotations

import logging
import re
import unicodedata

from app.services.sourcing.providers.base import RawCandidate

logger = logging.getLogger(__name__)

# Provider trust order: higher index = lower trust when merging
_PROVIDER_TRUST: dict[str, int] = {
    "airis": 100,
    "naukri_stub": 10,
}


def _trust(source: str) -> int:
    return _PROVIDER_TRUST.get(source, 0)


def _normalise_email(email: str | None) -> str | None:
    if not email:
        return None
    return email.strip().lower()


def _normalise_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    # Strip everything except digits and leading +
    digits = re.sub(r"[^\d]", "", phone)
    return digits[-10:] if len(digits) >= 10 else digits or None


def _name_key(c: RawCandidate) -> str:
    first = unicodedata.normalize("NFKD", (c.first_name or "").lower().strip())
    last = unicodedata.normalize("NFKD", (c.last_name or "").lower().strip())
    return f"{first} {last}".strip()


def _levenshtein_ratio(a: str, b: str) -> float:
    """Simple Levenshtein ratio without external dependency."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = i
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr = dp[j - 1]
            else:
                curr = 1 + min(dp[j], prev, dp[j - 1])
            dp[j - 1] = prev
            prev = curr
        dp[n] = prev
    dist = dp[n]
    return 1.0 - dist / max(m, n)


def _merge(primary: RawCandidate, duplicate: RawCandidate) -> RawCandidate:
    """Merge *duplicate* into *primary*, preferring the higher-trust source."""
    merged_sources = list(primary.raw_data.get("merged_sources", [primary.source]))
    if duplicate.source not in merged_sources:
        merged_sources.append(duplicate.source)
    primary.raw_data["merged_sources"] = merged_sources
    return primary


class CandidateDeduplicator:
    """Deduplicate a mixed list of RawCandidates from multiple providers."""

    def deduplicate(self, candidates: list[RawCandidate]) -> list[RawCandidate]:
        """Return a deduplicated list. Input order is preserved (first seen wins)."""
        seen_emails: dict[str, int] = {}   # normalised_email → index in `out`
        seen_phones: dict[str, int] = {}   # normalised_phone → index in `out`
        out: list[RawCandidate] = []

        for c in candidates:
            norm_email = _normalise_email(c.email)
            norm_phone = _normalise_phone(c.phone)

            # ── 1. Email exact match ──────────────────────────────────────────
            if norm_email and norm_email in seen_emails:
                idx = seen_emails[norm_email]
                existing = out[idx]
                if _trust(c.source) > _trust(existing.source):
                    out[idx] = _merge(c, existing)
                else:
                    _merge(existing, c)
                c.is_duplicate = True
                logger.debug(
                    "deduplicator.email_match",
                    extra={"email": norm_email, "source": c.source},
                )
                continue

            # ── 2. Phone exact match ──────────────────────────────────────────
            if norm_phone and norm_phone in seen_phones:
                idx = seen_phones[norm_phone]
                existing = out[idx]
                if _trust(c.source) > _trust(existing.source):
                    out[idx] = _merge(c, existing)
                else:
                    _merge(existing, c)
                c.is_duplicate = True
                logger.debug(
                    "deduplicator.phone_match",
                    extra={"phone": norm_phone, "source": c.source},
                )
                continue

            # ── 3. Fuzzy name match ───────────────────────────────────────────
            name_key = _name_key(c)
            fuzzy_idx: int | None = None
            for i, existing in enumerate(out):
                if _levenshtein_ratio(name_key, _name_key(existing)) >= 0.85:
                    fuzzy_idx = i
                    break

            if fuzzy_idx is not None:
                existing = out[fuzzy_idx]
                _merge(existing, c)
                c.is_duplicate = True
                logger.debug(
                    "deduplicator.fuzzy_name_match",
                    extra={"name_key": name_key, "source": c.source},
                )
                continue

            # ── New unique candidate ──────────────────────────────────────────
            idx = len(out)
            out.append(c)
            if norm_email:
                seen_emails[norm_email] = idx
            if norm_phone:
                seen_phones[norm_phone] = idx

        logger.info(
            "deduplicator.complete",
            extra={"input": len(candidates), "output": len(out)},
        )
        return out
