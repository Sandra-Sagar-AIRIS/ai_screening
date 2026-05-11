"""Resume text normalization for skill dictionary matching.

Raw resumes use many spellings (React.js, ReactJS, Node, Postgres). The ATS
extractor scans lowercase text with word-boundary regexes. Without collapsing
those variants to canonical tokens, common skills are missed (e.g. “react”
cannot match inside “react.js” because `.` blocks the boundary rule).

This module applies the same alias map as JD normalization plus punctuation
collapses so catalogue hits align with real resume typography.
"""
from __future__ import annotations

import re

from app.services.jd_normalization_service import SKILL_ALIASES

# Extra punctuation / spacing variants not worth polluting JD aliases with.
_EXTRA_RESUME_FIXES: tuple[tuple[str, str], ...] = (
    (r"\breact\.js\b", "react"),
    (r"\breactjs\b", "react"),
    (r"\bangular\.js\b", "angular"),
    (r"\bvue\.js\b", "vue"),
    (r"\bnext\.js\b", "next.js"),
    (r"\bnest\.js\b", "nestjs"),
    (r"\bnode\s*\.?\s*js\b", "node.js"),
    (r"\bpostgres(?:ql)?\b", "postgresql"),
    (r"\bmongo\s*db\b", "mongodb"),
    (r"\bmysql\b", "mysql"),
    (r"\brest(?:ful)?\s+apis?\b", "rest"),
    (r"\bagile\b", "agile"),
)


def normalize_resume_text_for_skill_matching(text: str) -> str:
    """Lowercase + alias + punctuation normalization for substring skill scans."""
    out = text.lower()
    # Longest alias keys first so multi-token forms win.
    for alias, canon in sorted(SKILL_ALIASES.items(), key=lambda kv: (-len(kv[0]), kv[0])):
        if not alias.strip():
            continue
        pat = rf"(?<![a-z0-9+/.\-]){re.escape(alias)}(?![a-z0-9+/.\-])"
        out = re.sub(pat, canon, out, flags=re.IGNORECASE)
    for pat, rep in _EXTRA_RESUME_FIXES:
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return out


_SKILL_LINE_SPLIT_RE = re.compile(r"[,;|•·\n\r]+")


def tokenize_skill_section_lines(skills_section: str) -> list[str]:
    """Split typical resume skill bullets/lines into raw tokens."""
    if not skills_section or not skills_section.strip():
        return []
    tokens: list[str] = []
    for raw_line in skills_section.splitlines():
        line = raw_line.strip().strip("-•*\t").strip()
        if not line or len(line) > 200:
            continue
        # Skip pure section headers
        if re.match(r"^(skills|technical skills|core competencies)\s*:?\s*$", line, re.I):
            continue
        for part in _SKILL_LINE_SPLIT_RE.split(line):
            t = part.strip()
            if 1 < len(t) < 80:
                tokens.append(t)
    return tokens
