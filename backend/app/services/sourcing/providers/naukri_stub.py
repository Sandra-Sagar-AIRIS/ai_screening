"""Naukri stub provider — returns deterministic test data.

THIS IS A DEVELOPMENT/DEMO STUB ONLY.
Replace with a real Naukri API integration before enabling in production.
"""
from __future__ import annotations

import logging
from uuid import UUID

from app.services.sourcing.providers.base import BaseCandidateProvider, RawCandidate, SourcingQuery

logger = logging.getLogger(__name__)

_STUB_CANDIDATES: list[dict] = [
    {
        "external_id": "naukri-stub-001",
        "first_name": "Priya",
        "last_name": "Sharma",
        "email": "priya.sharma.stub@naukri-demo.invalid",
        "phone": None,
        "location": "Bangalore, India",
        "title": "Senior Software Engineer",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker"],
        "experience_years": 5,
    },
    {
        "external_id": "naukri-stub-002",
        "first_name": "Rahul",
        "last_name": "Verma",
        "email": "rahul.verma.stub@naukri-demo.invalid",
        "phone": None,
        "location": "Hyderabad, India",
        "title": "Full Stack Developer",
        "skills": ["React", "Node.js", "MongoDB", "TypeScript"],
        "experience_years": 4,
    },
    {
        "external_id": "naukri-stub-003",
        "first_name": "Ananya",
        "last_name": "Krishnan",
        "email": "ananya.k.stub@naukri-demo.invalid",
        "phone": None,
        "location": "Chennai, India",
        "title": "Data Engineer",
        "skills": ["Python", "Spark", "Kafka", "Airflow"],
        "experience_years": 6,
    },
    {
        "external_id": "naukri-stub-004",
        "first_name": "Vikram",
        "last_name": "Singh",
        "email": "vikram.s.stub@naukri-demo.invalid",
        "phone": None,
        "location": "Pune, India",
        "title": "Backend Engineer",
        "skills": ["Java", "Spring Boot", "Microservices", "AWS"],
        "experience_years": 7,
    },
    {
        "external_id": "naukri-stub-005",
        "first_name": "Meera",
        "last_name": "Patel",
        "email": "meera.p.stub@naukri-demo.invalid",
        "phone": None,
        "location": "Mumbai, India",
        "title": "ML Engineer",
        "skills": ["Python", "TensorFlow", "PyTorch", "MLflow"],
        "experience_years": 3,
    },
]


class NaukriStubProvider(BaseCandidateProvider):
    """Stub — returns hardcoded candidates regardless of query. Dev/demo only."""

    provider_id = "naukri_stub"

    async def search(
        self,
        query: SourcingQuery,
        org_id: UUID,
        limit: int = 20,
    ) -> list[RawCandidate]:
        logger.debug(
            "naukri_stub.search",
            extra={"org_id": str(org_id), "title": query.title, "stub": True},
        )
        candidates = [
            RawCandidate(
                source=self.provider_id,
                external_id=c["external_id"],
                first_name=c["first_name"],
                last_name=c["last_name"],
                email=c["email"],
                phone=c["phone"],
                location=c["location"],
                title=c["title"],
                skills=c["skills"],
                experience_years=c["experience_years"],
                raw_data={"stub": True, "provider": "naukri"},
            )
            for c in _STUB_CANDIDATES
        ]
        return candidates[:limit]
