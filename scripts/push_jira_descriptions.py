#!/usr/bin/env python3
"""Push refined descriptions to Jira issues (ADF)."""
from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path


def load_env() -> dict[str, str]:
    p = Path(__file__).resolve().parents[1] / "backend" / ".env"
    out: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("JIRA_") and "=" in line:
            k, v = line.split("=", 1)
            out[k] = v
    return out


def adf_doc(blocks: list[dict]) -> dict:
    return {"type": "doc", "version": 1, "content": blocks}


def heading(text: str, level: int = 2) -> dict:
    return {
        "type": "heading",
        "attrs": {"level": level},
        "content": [{"type": "text", "text": text}],
    }


def paragraph(text: str, *, bold_prefix: str | None = None) -> dict:
    if bold_prefix:
        return {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": bold_prefix, "marks": [{"type": "strong"}]},
                {"type": "text", "text": text},
            ],
        }
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def bullet_list(items: list[str]) -> dict:
    return {
        "type": "bulletList",
        "content": [
            {
                "type": "listItem",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": item}]}],
            }
            for item in items
        ],
    }


def build_air37() -> dict:
    return adf_doc(
        [
            heading("User story"),
            paragraph(
                "As a recruiter, I want one read-only placement history per candidate so I can see every job submission and pipeline outcome without changing past records."
            ),
            heading("What it does"),
            bullet_list(
                [
                    "Placement History tab on the candidate profile",
                    "Lists jobs submitted, outcomes (pending / placed / rejected), and pipeline stage events",
                    "Newest first; rejection reasons expandable on rejected rows",
                    "Append-only — no edit or delete",
                ]
            ),
            heading("Acceptance criteria"),
            bullet_list(
                [
                    "GET /api/v1/candidates/{id}/placements returns full history",
                    "Each row: job title, outcome, date (newest first)",
                    "Rejection reason visible when outcome is rejected",
                    "History is immutable (append-only writes only)",
                    "Pipeline stage changes recorded automatically",
                ]
            ),
            heading("Delivered"),
            bullet_list(
                [
                    "PlacementHistoryService + candidate_placement_history table",
                    "PlacementHistoryTab UI",
                    "Automated tests (AIR-37)",
                ]
            ),
            heading("Demo"),
            paragraph("Candidate profile → Placement History → show table, expand a rejection if present."),
            heading("Meta"),
            paragraph(
                "Feature ID: CAND-008 | Module: Candidate Management | Priority: High | Points: 5 | Dependencies: CAND-002, PIPE-001"
            ),
        ]
    )


def build_air38() -> dict:
    return adf_doc(
        [
            heading("User story"),
            paragraph(
                "As a recruiter, I want timestamped notes on a candidate profile with author attribution, so my team shares context without deleting history."
            ),
            heading("What it does"),
            bullet_list(
                [
                    "Notes panel on candidate profile — add, list, author + time on every note",
                    "Notes stored as candidate interactions (type: note)",
                    "Admins can soft-hide a note from the team; notes are never hard-deleted",
                    "Notes appear in Communication Hub timeline when filtering by Notes",
                ]
            ),
            heading("Acceptance criteria"),
            bullet_list(
                [
                    "POST /api/v1/candidates/{id}/notes — create with author and timestamp",
                    "GET /api/v1/candidates/{id}/notes — list for users with candidate access",
                    "Author and created time displayed in UI",
                    "Admin-only POST .../notes/{note_id}/hide — soft-hide (metadata.hidden)",
                    "No hard delete for notes",
                ]
            ),
            heading("Pending"),
            bullet_list(
                [
                    "Notes searchable via global candidate list search (note body not indexed yet)",
                ]
            ),
            heading("Delivered"),
            bullet_list(
                [
                    "candidate_notes routes + CandidateNotesPanel",
                    "soft_hide_note (AIR-508) for admins",
                    "Timeline integration via interactions API",
                ]
            ),
            heading("Demo"),
            paragraph("Candidate profile → add note → show author/time → (admin) hide note."),
            heading("Meta"),
            paragraph(
                "Feature ID: CAND-009 | Module: Candidate Management | Priority: High | Points: 5 | Dependencies: CAND-002"
            ),
        ]
    )


def build_air39() -> dict:
    return adf_doc(
        [
            heading("User story"),
            paragraph(
                "As an admin, I want to archive candidates without permanent data loss, so lists stay accurate and records can be restored when needed."
            ),
            heading("What it does"),
            bullet_list(
                [
                    "Soft delete marks candidate deleted and hides from lists/search",
                    "Active pipelines withdrawn on archive",
                    "Audit log + system interaction on archive/restore",
                    "Admin restore via PATCH restore endpoint",
                ]
            ),
            heading("Acceptance criteria"),
            bullet_list(
                [
                    "DELETE /api/v1/candidates/{id} archives candidate (not hard delete)",
                    "Archived candidates excluded from list and search",
                    "PATCH /api/v1/candidates/{id}/restore — admin only",
                    "Deletion/restoration logged in audit trail",
                    "Pipelines withdrawn when candidate archived",
                ]
            ),
            heading("Delivered"),
            bullet_list(
                [
                    "archive/soft_delete + restore in CandidateManagementService",
                    "withdraw_active_pipelines_for_candidate",
                    "Audit log entries and API routes on /api/v1 and candidate-management",
                ]
            ),
            heading("Demo"),
            paragraph("Archive test candidate → gone from list → restore as admin → back in list."),
            heading("Meta"),
            paragraph(
                "Feature ID: CAND-010 | Module: Candidate Management | Priority: Medium | Points: 3 | Dependencies: CAND-002"
            ),
        ]
    )


DESCRIPTIONS = {
    "AIR-37": build_air37(),
    "AIR-38": build_air38(),
    "AIR-39": build_air39(),
}


def api_request(method: str, url: str, auth: str, body: dict | None = None) -> dict | None:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Basic {auth}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else None


def main() -> None:
    env = load_env()
    email = env.get("JIRA_AUTH_EMAIL") or env["JIRA_EMAIL"]
    token = env["JIRA_API_TOKEN"]
    base = env["JIRA_BASE_URL"].rstrip("/")
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()

    for key, description in DESCRIPTIONS.items():
        api_request(
            "PUT",
            f"{base}/rest/api/3/issue/{key}",
            auth,
            {"fields": {"description": description}},
        )
        print(f"Updated description: {key}")

    # AIR-38: move to To Do (pending search AC)
    transitions = api_request("GET", f"{base}/rest/api/3/issue/AIR-38/transitions", auth)
    todo_id = next(t["id"] for t in transitions["transitions"] if t["name"] == "To Do")
    api_request(
        "POST",
        f"{base}/rest/api/3/issue/AIR-38/transitions",
        auth,
        {"transition": {"id": todo_id}},
    )
    print("Transitioned AIR-38 → To Do")

    comment = adf_doc(
        [
            paragraph(
                "Description refined for standup/daily review. Moved back to To Do: global candidate search does not yet index note body text (profile + Communication Hub timeline are done)."
            ),
        ]
    )
    api_request(
        "POST",
        f"{base}/rest/api/3/issue/AIR-38/comment",
        auth,
        {"body": comment},
    )
    print("Added comment on AIR-38")


if __name__ == "__main__":
    main()
