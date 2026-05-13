from __future__ import annotations

import html
from pathlib import Path


def docx_body_html_from_path(file_path: Path) -> str:
    """Convert DOCX paragraphs to a small safe HTML fragment (no scripts)."""
    from docx import Document

    document = Document(str(file_path))
    parts: list[str] = []
    in_list = False
    for paragraph in document.paragraphs:
        raw = paragraph.text or ""
        if not raw.strip():
            if in_list:
                parts.append("</ul>")
                in_list = False
            continue

        style_name = (paragraph.style.name or "").lower() if paragraph.style is not None else ""
        run_html = "".join(
            (
                f"<strong>{html.escape(run.text)}</strong>"
                if run.bold
                else f"<em>{html.escape(run.text)}</em>"
                if run.italic
                else html.escape(run.text)
            )
            for run in paragraph.runs
            if (run.text or "")
        ).strip()
        if not run_html:
            run_html = html.escape(raw.strip())

        if "list" in style_name:
            if not in_list:
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{run_html}</li>")
            continue

        if in_list:
            parts.append("</ul>")
            in_list = False

        if "heading" in style_name or (paragraph.style and paragraph.style.name in {"Title", "Subtitle"}):
            parts.append(f"<h3>{run_html}</h3>")
        else:
            parts.append(f"<p>{run_html}</p>")

    if in_list:
        parts.append("</ul>")
    if not parts:
        parts.append("<p>No previewable text found in this DOCX file.</p>")
    return "".join(parts)


def wrap_document_preview_html(*, title: str, display_name: str, body_html: str) -> str:
    safe_title = html.escape(title)
    safe_meta = html.escape(display_name)
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{safe_title}</title>"
        "<style>"
        "body{margin:0;background:#f8fafc;font-family:Inter,Segoe UI,Arial,sans-serif;color:#0f172a;}"
        ".wrap{max-width:900px;margin:24px auto;padding:24px;background:#fff;border:1px solid #e2e8f0;border-radius:12px;}"
        ".meta{font-size:13px;color:#64748b;margin-bottom:14px;}"
        "h3{margin:18px 0 8px;font-size:18px;line-height:1.3;}"
        "p{margin:8px 0;line-height:1.6;white-space:pre-wrap;}"
        "ul{margin:8px 0 8px 20px;line-height:1.6;}"
        "li{margin:4px 0;}"
        "</style></head><body>"
        f"<div class='wrap'><div class='meta'>{safe_meta}</div>{body_html}</div>"
        "</body></html>"
    )
