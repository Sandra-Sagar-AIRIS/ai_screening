from __future__ import annotations

from app.services.ats_extraction_service import ATSExtractionService
from app.services.resume_parser import ParsedResume


def test_extracts_common_tech_from_free_text_variants() -> None:
    """React.js and similar forms must match after alias/punctuation normalization."""
    text = """
    Jane Doe
    Skills: React.js, Node.js, REST APIs, MySQL, MongoDB, PostgreSQL, Agile
    Experience: Senior Engineer at Acme 2020–Present
    """
    parsed = ParsedResume(text=text, sections={}, parser="pdfplumber", page_count=1)
    svc = ATSExtractionService()
    profile = svc.extract(parsed)
    skills = set(profile.skills)
    assert "react" in skills
    assert "node.js" in skills or "nodejs" in skills  # alias normalizes to node.js
    assert "mysql" in skills
    assert "mongodb" in skills
    assert "postgresql" in skills
    assert "agile" in skills


def test_skills_section_comma_tokens() -> None:
    body = "React.js | Vue.js | Terraform\nDocker\nKubernetes"
    parsed = ParsedResume(
        text="Header\n" + body,
        sections={"skills": body},
        parser="python-docx",
        page_count=1,
    )
    svc = ATSExtractionService()
    profile = svc.extract(parsed)
    assert "react" in profile.skills
    assert "docker" in profile.skills
