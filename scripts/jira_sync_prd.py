#!/usr/bin/env python3
"""
Sync AIRIS PRD user stories (v1.0) to Jira Cloud: create missing Stories + Sub-tasks,
optionally transition implemented items to Done.

Requires Jira Cloud REST (no MCP): install Atlassian app or use API token.

Environment (or .env next to this file / repo root):
  JIRA_BASE_URL   e.g. https://your-site.atlassian.net
  JIRA_EMAIL      Often your work email (shown in app)
  JIRA_AUTH_EMAIL Optional — if set, used for Basic auth with the API token (use when this must
                  match your Atlassian id.atlassian.com primary email exactly)
  JIRA_API_TOKEN  https://id.atlassian.com/manage-profile/security/api-tokens
  JIRA_PROJECT_KEY  e.g. AIR

Usage:
  python scripts/jira_sync_prd.py --verify-auth
  python scripts/jira_sync_prd.py --dry-run
  python scripts/jira_sync_prd.py --sync
  python scripts/jira_sync_prd.py --sync --transition-done

Optional:
  --prd-path PATH     default: docs/prds/airis-recruiting-platform-prd-v1.0.md
  --implemented-json PATH   default: scripts/jira_implemented.json (key story_numbers_done)
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

LABEL = "airis-prd-v1"
# Short label per story for reliable JQL (avoids US-1 matching US-10)
def story_label(n: int) -> str:
    return f"airis-us-{n}"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


_JIRA_LINE = re.compile(r"^\s*(JIRA_[A-Z0-9_]+)\s*=\s*(.*)$", re.IGNORECASE)


def _clean_env_value(raw: str) -> str:
    """Strip quotes/whitespace and stray CRs (Windows editors)."""
    return raw.strip().strip('"').strip("'").replace("\r", "")


def _load_dotenv() -> dict[str, str]:
    """Apply JIRA_* from .env files. Returns map of key -> relative path that last set it."""
    merged: dict[str, str] = {}
    sources: dict[str, str] = {}
    for rel in (".env", "backend/.env"):
        p = _repo_root() / rel
        if not p.is_file():
            continue
        for raw_line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.lstrip("\ufeff").strip()
            if not line or line.startswith("#"):
                continue
            m = _JIRA_LINE.match(line)
            if not m:
                continue
            k = m.group(1).upper()
            merged[k] = _clean_env_value(m.group(2))
            sources[k] = rel
    for k, v in merged.items():
        if not v:
            continue
        existing = os.environ.get(k, "").strip()
        if k not in os.environ or not existing:
            os.environ[k] = v
    return sources


def parse_prd_stories(prd_path: Path) -> list[dict[str, Any]]:
    text = prd_path.read_text(encoding="utf-8", errors="replace")
    stories: list[dict[str, Any]] = []
    # Lines like: 10. As a recruiter, I want X, so that Y.
    pat = re.compile(
        r"^(\d+)\.\s+As\s+(.+?),\s+I want\s+(.+?),\s+so that\s+(.+?)\.\s*$",
        re.MULTILINE,
    )
    for m in pat.finditer(text):
        num = int(m.group(1))
        actor = m.group(2).strip()
        want = m.group(3).strip()
        benefit = m.group(4).strip()
        stories.append(
            {
                "num": num,
                "actor": actor,
                "want": want,
                "benefit": benefit,
                "full": m.group(0).strip(),
            }
        )
    stories.sort(key=lambda s: s["num"])
    return stories


def adf_doc(paragraphs: list[str]) -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    for para in paragraphs:
        content.append(
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": para}],
            }
        )
    return {"type": "doc", "version": 1, "content": content}


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str) -> None:
        self.base = base_url.rstrip("/")
        raw = f"{email}:{api_token}".encode()
        self._auth = "Basic " + base64.b64encode(raw).decode()

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base}{path}"
        data = None
        headers = {
            "Authorization": self._auth,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code} {e.reason}: {err}") from e

    def jql_search(self, jql: str, *, max_results: int = 50) -> list[dict[str, Any]]:
        body = {
            "jql": jql,
            "maxResults": max_results,
            "fields": ["summary", "status", "issuetype", "parent"],
        }
        out = self._request("POST", "/rest/api/3/search", body=body)
        return list(out.get("issues") or [])

    def create_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        description_adf: dict[str, Any],
        *,
        labels: list[str],
        parent_key: str | None = None,
    ) -> str:
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary[:254],
            "description": description_adf,
            "issuetype": {"name": issue_type},
            "labels": labels,
        }
        if parent_key:
            fields["parent"] = {"key": parent_key}
        body = {"fields": fields}
        created = self._request("POST", "/rest/api/3/issue", body=body)
        return str(created["key"])

    def get_transitions(self, issue_key: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/rest/api/3/issue/{issue_key}/transitions")
        return list(data.get("transitions") or [])

    def transition(self, issue_key: str, transition_id: str) -> None:
        body = {"transition": {"id": transition_id}}
        self._request("POST", f"/rest/api/3/issue/{issue_key}/transitions", body=body)

    def get_myself(self) -> dict[str, Any]:
        return self._request("GET", "/rest/api/3/myself")

    def get_project(self, project_key: str) -> dict[str, Any]:
        return self._request("GET", f"/rest/api/3/project/{project_key}")


def default_subtasks(story: dict[str, Any]) -> list[str]:
    n = story["num"]
    return [
        f"US-{n}: Backend / API & data model",
        f"US-{n}: Frontend / UX",
        f"US-{n}: QA, permissions, and acceptance criteria sign-off",
    ]


def find_done_transition_id(client: JiraClient, issue_key: str) -> str | None:
    for tr in client.get_transitions(issue_key):
        name = (tr.get("name") or "").strip().lower()
        if name in ("done", "closed", "complete", "resolved"):
            return str(tr["id"])
    for tr in client.get_transitions(issue_key):
        to = (tr.get("to") or {}).get("name") or ""
        if str(to).strip().lower() in ("done", "closed", "complete", "resolved"):
            return str(tr["id"])
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync AIRIS PRD stories to Jira Cloud")
    parser.add_argument("--dry-run", action="store_true", help="Print actions only")
    parser.add_argument("--sync", action="store_true", help="Create missing issues in Jira")
    parser.add_argument(
        "--transition-done",
        action="store_true",
        help="Transition issues listed in jira_implemented.json to Done/Closed",
    )
    parser.add_argument(
        "--prd-path",
        type=Path,
        default=_repo_root() / "docs/prds/airis-recruiting-platform-prd-v1.0.md",
    )
    parser.add_argument(
        "--implemented-json",
        type=Path,
        default=_repo_root() / "scripts/jira_implemented.json",
    )
    parser.add_argument(
        "--verify-auth",
        action="store_true",
        help="Check JIRA_* from .env / backend/.env against Jira API (no issue creation)",
    )
    args = parser.parse_args()

    jira_sources = _load_dotenv()

    base = os.environ.get("JIRA_BASE_URL", "").strip()
    email = os.environ.get("JIRA_EMAIL", "").strip()
    auth_email = os.environ.get("JIRA_AUTH_EMAIL", "").strip() or email
    token = os.environ.get("JIRA_API_TOKEN", "").strip()
    project = os.environ.get("JIRA_PROJECT_KEY", "").strip()

    if args.verify_auth:
        if not all([base, auth_email, token, project]):
            print(
                "Missing JIRA_BASE_URL, JIRA_EMAIL (or JIRA_AUTH_EMAIL), JIRA_API_TOKEN, "
                "and/or JIRA_PROJECT_KEY "
                "(set in repo .env or backend/.env — keys must be prefixed JIRA_).",
                file=sys.stderr,
            )
            return 1
        try:
            client = JiraClient(base, auth_email, token)
            me = client.get_myself()
            proj = client.get_project(project)
        except RuntimeError as e:
            print(f"Jira API error: {e}", file=sys.stderr)
            err = str(e).lower()
            if "401" in err or "unauthorized" in err:
                tl = len(token)
                src = ", ".join(
                    f"{k}←{jira_sources.get(k, '?')}"
                    for k in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN", "JIRA_PROJECT_KEY")
                    if os.environ.get(k)
                )
                print(
                    f"401 checklist: (1) API token from id.atlassian.com for the SAME account as Basic auth email. "
                    f"(2) Basic auth email is currently: {auth_email!r} — if wrong, set JIRA_AUTH_EMAIL to your "
                    f"Atlassian account primary email. (3) Token must be one continuous line in .env (no wrap). "
                    f"(4) Site URL matches your Jira: {base!r}.",
                    file=sys.stderr,
                )
                print(f"Token length={tl} (183+ can be valid). Loaded: {src}", file=sys.stderr)
            return 1
        auth_suffix = (
            f" | Basic auth user: {auth_email}"
            if os.environ.get("JIRA_AUTH_EMAIL", "").strip()
            else ""
        )
        print(
            "OK: authenticated as "
            f"{me.get('displayName', me.get('emailAddress', '?'))} "
            f"| project {proj.get('key')}: {proj.get('name', '')}"
            + auth_suffix
        )
        return 0

    prd_path = args.prd_path.resolve()
    if not prd_path.is_file():
        print(f"PRD not found: {prd_path}", file=sys.stderr)
        return 1

    stories = parse_prd_stories(prd_path)
    if not stories:
        print("No numbered user stories parsed from PRD.", file=sys.stderr)
        return 1

    done_nums: set[int] = set()
    if args.implemented_json.is_file():
        data = json.loads(args.implemented_json.read_text(encoding="utf-8"))
        done_nums = {int(x) for x in data.get("story_numbers_done", [])}

    print(f"Parsed {len(stories)} stories from {prd_path}")
    print(f"Shared label: {LABEL}; per-story label example: {story_label(10)}")
    print(f"Transition to Done for PRD numbers (when --transition-done): {sorted(done_nums) if done_nums else '(none)'}")

    if args.dry_run:
        if args.sync:
            print("\n[dry-run] Would create missing stories + 3 subtasks each (no API calls).")
            for s in stories[:3]:
                print(f"  US-{s['num']}: [AIRIS US-{s['num']}] {s['want'][:80]}…")
            if len(stories) > 3:
                print(f"  … plus {len(stories) - 3} more stories")
        if args.transition_done:
            print(f"\n[dry-run] Would transition Done for US numbers: {sorted(done_nums)}")
        if not args.sync and not args.transition_done:
            print("\n[dry-run] Pass --sync and/or --transition-done to preview side effects.")
        return 0

    if (args.sync or args.transition_done) and not all([base, auth_email, token, project]):
        print(
            "Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN, JIRA_PROJECT_KEY (see script docstring).",
            file=sys.stderr,
        )
        return 1

    if not args.sync and not args.transition_done:
        print("\nRe-run with --sync and/or --transition-done after setting env vars.")
        return 0

    client = JiraClient(base, auth_email, token)

    story_type = os.environ.get("JIRA_STORY_ISSUE_TYPE", "Story").strip()
    subtask_type = os.environ.get("JIRA_SUBTASK_ISSUE_TYPE", "Sub-task").strip()

    if args.sync:
        for s in stories:
            n = s["num"]
            slab = story_label(n)
            jql = f'project = {project} AND labels = "{slab}" AND issuetype = "{story_type}"'
            existing = client.jql_search(jql, max_results=5)
            if existing:
                print(f"Skip US-{n} (exists): {existing[0].get('key')}")
                continue
            summary = f"[AIRIS US-{n}] {s['want'][:200]}"
            desc = adf_doc(
                [
                    s["full"],
                    "",
                    f"Actor: {s['actor']}",
                    f"Benefit: {s['benefit']}",
                    "",
                    f"Source: {prd_path.as_posix()}",
                ]
            )
            key = client.create_issue(
                project,
                story_type,
                summary,
                desc,
                labels=[LABEL, slab],
            )
            print(f"Created {story_type} {key} for US-{n}")
            for st in default_subtasks(s):
                sk = client.create_issue(
                    project,
                    subtask_type,
                    st,
                    adf_doc([f"Parent PRD story: US-{n}", "", s["full"]]),
                    labels=[LABEL, slab],
                    parent_key=key,
                )
                print(f"  {subtask_type} {sk}")

    if args.transition_done:
        for n in sorted(done_nums):
            slab = story_label(n)
            jql = f'project = {project} AND labels = "{slab}" AND issuetype = "{story_type}"'
            issues = client.jql_search(jql, max_results=3)
            if not issues:
                print(f"No Jira issue found for US-{n} (create with --sync first)", file=sys.stderr)
                continue
            issue_key = str(issues[0]["key"])
            tid = find_done_transition_id(client, issue_key)
            if not tid:
                print(f"No Done-like transition for {issue_key} (US-{n})", file=sys.stderr)
                continue
            status = (issues[0].get("fields") or {}).get("status", {}).get("name", "")
            if str(status).lower() in ("done", "closed", "complete", "resolved"):
                print(f"Already terminal: {issue_key} US-{n} ({status})")
                continue
            client.transition(issue_key, tid)
            print(f"Transitioned {issue_key} (US-{n}) -> Done")
            # Close sub-tasks under this story when possible
            subs = client.jql_search(f"parent = {issue_key}", max_results=50)
            for sub in subs:
                sk = str(sub["key"])
                st_name = ((sub.get("fields") or {}).get("status") or {}).get("name", "")
                if str(st_name).lower() in ("done", "closed", "complete", "resolved"):
                    continue
                stid = find_done_transition_id(client, sk)
                if stid:
                    client.transition(sk, stid)
                    print(f"  Sub-task {sk} -> Done")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
