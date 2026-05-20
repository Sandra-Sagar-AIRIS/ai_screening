"""Base provider abstraction for AI candidate sourcing.

Adding a new data source requires:
1. Subclass BaseCandidateProvider
2. Implement search()
3. Register in registry.py
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from uuid import UUID


@dataclass
class SourcingQuery:
    """Structured search parameters derived from a job description."""

    title: str
    skills: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    location: str | None = None
    experience_min: int | None = None
    experience_max: int | None = None


@dataclass
class RawCandidate:
    """Normalised candidate record returned by any provider before scoring."""

    source: str                          # provider_id e.g. "airis", "naukri_stub"
    first_name: str
    last_name: str
    external_id: str | None = None       # provider's own ID (or AIRIS UUID for internal)
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    title: str | None = None
    skills: list[str] = field(default_factory=list)
    experience_years: int | None = None
    resume_url: str | None = None
    raw_data: dict = field(default_factory=dict)
    is_duplicate: bool = False


class BaseCandidateProvider(ABC):
    """Abstract base for all candidate data sources."""

    provider_id: str = "base"

    @abstractmethod
    async def search(
        self,
        query: SourcingQuery,
        org_id: UUID,
        limit: int = 20,
    ) -> list[RawCandidate]:
        """Search for candidates matching *query* within *org_id*.

        Must never raise — return an empty list on failure (log the error).
        """
