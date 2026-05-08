from __future__ import annotations

from app.services.jd_normalization_service import JDNormalizationService


def test_jd_normalization_dedupes_and_applies_aliases() -> None:
    service = JDNormalizationService()
    normalized = service.normalize(
        required_skills=["Python", "  python  ", "K8s", "NodeJS"],
        preferred_skills=["node", "Docker", "kubernetes"],
    )
    assert normalized.required_skills_normalized == ["python", "kubernetes", "node.js"]
    # preferred should exclude values already in required
    assert normalized.preferred_skills_normalized == ["docker"]

