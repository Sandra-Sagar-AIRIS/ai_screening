#!/usr/bin/env python3
"""Fetch Jira issues by key and print summary for standup."""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.request
from pathlib import Path


def load_env() -> dict[str, str]:
    for p in (
        Path(__file__).resolve().parents[1] / "backend" / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ):
        if not p.exists():
            continue
        out: dict[str, str] = {}
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("JIRA_") and "=" in line:
                k, v = line.split("=", 1)
                out[k] = v
        return out
    raise SystemExit("No JIRA_* in backend/.env")


def adf_to_text(node: dict | None) -> str:
    if not node:
        return ""
    t = node.get("type")
    if t == "text":
        return node.get("text", "")
    if t == "hardBreak":
        return "\n"
    parts = [adf_to_text(c) for c in node.get("content") or []]
    text = "".join(parts)
    if t in ("paragraph", "heading"):
        return text + "\n"
    if t == "bulletList":
        lines = []
        for li in node.get("content") or []:
            item = adf_to_text(li).strip()
            if item:
                lines.append(f"  - {item}")
        return "\n".join(lines) + ("\n" if lines else "")
    if t == "orderedList":
        lines = []
        for i, li in enumerate(node.get("content") or [], 1):
            item = adf_to_text(li).strip()
            if item:
                lines.append(f"  {i}. {item}")
        return "\n".join(lines) + ("\n" if lines else "")
    return text


def fetch_issue(base: str, auth: str, key: str) -> dict:
    url = f"{base}/rest/api/3/issue/{key}?fields=summary,status,description,issuetype,priority,assignee,parent,created,updated"
    req = urllib.request.Request(url, headers={"Authorization": f"Basic {auth}", "Accept": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def main() -> None:
    keys = sys.argv[1:] or ["AIR-37", "AIR-38", "AIR-39"]
    env = load_env()
    email = env.get("JIRA_AUTH_EMAIL") or env["JIRA_EMAIL"]
    token = env["JIRA_API_TOKEN"]
    base = env["JIRA_BASE_URL"].rstrip("/")
    auth = base64.b64encode(f"{email}:{token}".encode()).decode()

    for key in keys:
        data = fetch_issue(base, auth, key)
        f = data["fields"]
        desc = adf_to_text(f.get("description")).strip()
        assignee = (f.get("assignee") or {}).get("displayName") or "Unassigned"
        parent = f.get("parent")
        parent_s = f"{parent['key']} — {parent['fields']['summary']}" if parent else "—"
        print("=" * 60)
        print(f"{data['key']} | {f['summary']}")
        print(f"Status: {f['status']['name']} | {f['issuetype']['name']} | {f['priority']['name']}")
        print(f"Assignee: {assignee} | Parent: {parent_s}")
        print(f"Updated: {f.get('updated', '—')}")
        print("---")
        print(desc or "(no description)")
        print()


if __name__ == "__main__":
    main()
