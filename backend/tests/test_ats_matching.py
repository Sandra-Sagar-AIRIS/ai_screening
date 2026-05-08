from __future__ import annotations

from app.services.ats_matching_service import ATSMatchingService, CandidateScoringInput, JobScoringInput


def test_ats_scoring_strong_match() -> None:
    service = ATSMatchingService()
    result = service.score(
        candidate=CandidateScoringInput(
            candidate_id="c1",
            skills=["python", "fastapi", "postgresql", "docker"],
            years_of_experience=6,
            previous_titles=["Senior Backend Engineer"],
            education=["B.Tech Computer Science"],
            parser_confidence=0.9,
        ),
        job=JobScoringInput(
            job_id="j1",
            title="Backend Engineer",
            required_skills_normalized=["python", "fastapi"],
            preferred_skills_normalized=["docker", "kubernetes"],
            min_experience_years=4,
            education_requirements=["bachelor"],
        ),
    )
    assert result.match_score >= 85
    assert result.recommendation == "Strong Match"
    assert "python" in result.matched_skills


def test_ats_scoring_weak_match_when_missing_required() -> None:
    service = ATSMatchingService()
    result = service.score(
        candidate=CandidateScoringInput(
            candidate_id="c2",
            skills=["excel"],
            years_of_experience=1,
            previous_titles=["Intern"],
            education=[],
            parser_confidence=0.5,
        ),
        job=JobScoringInput(
            job_id="j2",
            title="Senior Python Engineer",
            required_skills_normalized=["python", "fastapi", "postgresql"],
            preferred_skills_normalized=["docker"],
            min_experience_years=5,
            education_requirements=["bachelor"],
        ),
    )
    assert result.match_score < 50
    assert result.recommendation == "Weak Match"
    assert set(result.missing_skills) >= {"python", "fastapi", "postgresql"}

