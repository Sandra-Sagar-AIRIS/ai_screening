from __future__ import annotations

import os
from typing import Final

import httpx


DEFAULT_BUCKET: Final[str] = "resumes"


class SupabaseStorageClient:
    def __init__(self) -> None:
        self.supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")
        self.bucket = os.getenv("SUPABASE_STORAGE_BUCKET", DEFAULT_BUCKET)
        self.timeout_seconds = float(os.getenv("SUPABASE_STORAGE_TIMEOUT_SECONDS", "30"))

    def is_configured(self) -> bool:
        return bool(self.supabase_url and self.service_key and self.bucket)

    def upload_bytes(self, *, object_key: str, content: bytes, content_type: str | None = None) -> str:
        if not self.is_configured():
            raise RuntimeError(
                "Supabase storage is not configured. Set SUPABASE_URL, "
                "SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY), and SUPABASE_STORAGE_BUCKET."
            )

        url = f"{self.supabase_url}/storage/v1/object/{self.bucket}/{object_key}"
        headers = {
            "apikey": self.service_key,
            "Authorization": f"Bearer {self.service_key}",
            "x-upsert": "true",
            "Content-Type": content_type or "application/octet-stream",
        }
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, headers=headers, content=content)
            response.raise_for_status()
        return object_key

