"""Supabase Storage service for AI screening interview recordings.

Storage layout:
  recordings/{screening_id}/
    interview.webm       — full raw recording
    transcript.json      — full conversation transcript
    analysis.json        — per-question timing + transcript data
    segments/
      q1.webm            — per-question video clips (browser-captured)
      q2.webm
      ...
"""
from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

from app.candidate_management.storage import SupabaseStorageClient

logger = logging.getLogger(__name__)

_RECORDINGS_BUCKET = "recordings"


def _client() -> SupabaseStorageClient:
    """Return a storage client configured for the recordings bucket."""
    import os
    client = SupabaseStorageClient()
    # Override bucket to recordings
    client.bucket = os.getenv("SUPABASE_RECORDINGS_BUCKET", _RECORDINGS_BUCKET)
    return client


def upload_interview_video(screening_id: UUID, video_bytes: bytes) -> str:
    """Upload the full interview WebM recording. Returns the Supabase object key."""
    key = f"recordings/{screening_id}/interview.webm"
    client = _client()
    if not client.is_configured():
        logger.warning("interview_storage: Supabase not configured — skipping video upload")
        return ""
    client.upload_bytes(object_key=key, content=video_bytes, content_type="video/webm")
    logger.info("interview_storage.video_uploaded screening=%s size=%d", screening_id, len(video_bytes))
    return key


def upload_segment_video(
    screening_id: UUID, question_number: int, video_bytes: bytes
) -> str:
    """Upload a per-question answer clip. Returns the Supabase object key."""
    key = f"recordings/{screening_id}/segments/q{question_number}.webm"
    client = _client()
    if not client.is_configured():
        logger.warning(
            "interview_storage: Supabase not configured — skipping segment q%d",
            question_number,
        )
        return ""
    client.upload_bytes(object_key=key, content=video_bytes, content_type="video/webm")
    logger.info(
        "interview_storage.segment_uploaded screening=%s q=%d size=%d",
        screening_id, question_number, len(video_bytes),
    )
    return key


def upload_transcript(screening_id: UUID, transcript: list[dict[str, Any]]) -> str:
    """Upload the full conversation transcript as JSON."""
    key = f"recordings/{screening_id}/transcript.json"
    client = _client()
    if not client.is_configured():
        return ""
    payload = json.dumps(transcript, ensure_ascii=False, indent=2).encode()
    client.upload_bytes(object_key=key, content=payload, content_type="application/json")
    return key


def upload_analysis(screening_id: UUID, analysis: dict[str, Any]) -> str:
    """Upload the per-question timing and evaluation data as JSON."""
    key = f"recordings/{screening_id}/analysis.json"
    client = _client()
    if not client.is_configured():
        return ""
    payload = json.dumps(analysis, ensure_ascii=False, indent=2).encode()
    client.upload_bytes(object_key=key, content=payload, content_type="application/json")
    return key


def get_signed_url(object_key: str, expires_in: int = 3600) -> str:
    """Return a signed download URL for a stored object."""
    if not object_key:
        return ""
    client = _client()
    if not client.is_configured():
        return ""
    try:
        return client.create_signed_download_url(
            object_key=object_key, expires_in_seconds=expires_in
        )
    except Exception as exc:
        logger.warning("interview_storage.signed_url_failed key=%s: %s", object_key, exc)
        return ""
