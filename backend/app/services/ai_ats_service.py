"""Low-level xAI Grok client for ATS enrichment.

OpenAI-compatible chat completions. Used only from background rescore paths;
never required for synchronous recruiter reads.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class GrokUnavailableError(Exception):
    """Raised when Grok cannot return a usable response (caller should fall back)."""


def _redact_messages_for_log(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for m in messages:
        content = m.get("content", "")
        if isinstance(content, str) and len(content) > 400:
            content = content[:400] + "…"
        out.append({"role": m.get("role", ""), "content": content})
    return out


class GrokAtsClient:
    """Centralized Grok HTTP client with timeout and retries."""

    def __init__(self) -> None:
        s = get_settings()
        self._api_key = (s.grok_api_key or "").strip()
        self._base = (s.grok_api_base or "https://api.x.ai/v1").rstrip("/")
        self._model = s.grok_model or "grok-2-latest"
        self._timeout = float(s.grok_timeout_seconds or 10.0)

    def is_configured(self) -> bool:
        return bool(self._api_key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)),
    )
    def chat_json_system_user(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.15,
    ) -> str:
        """Return assistant message content (must be JSON)."""
        if not self.is_configured():
            raise GrokUnavailableError("GROK_API_KEY not set")

        url = f"{self._base}/chat/completions"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        def _attempt(model: str) -> httpx.Response:
            payload: dict[str, Any] = {
                "model": model,
                "temperature": temperature,
                "messages": messages,
            }
            logger.info(
                "grok_ats_request model=%s timeout=%s messages=%s",
                model,
                self._timeout,
                json.dumps(_redact_messages_for_log(messages)),
            )
            with httpx.Client(timeout=self._timeout) as client:
                return client.post(url, headers=headers, json=payload)

        # Some accounts do not have access to all model aliases. If the model
        # is invalid, retry once with a safe fallback set.
        t0 = time.monotonic()
        resp = _attempt(self._model)
        if resp.status_code == 400 and "Model not found" in (resp.text or ""):
            for fallback_model in ("grok-3-mini", "grok-3"):
                if fallback_model == self._model:
                    continue
                resp = _attempt(fallback_model)
                if resp.status_code < 400:
                    break

        if resp.status_code >= 400:
            logger.warning(
                "grok_ats_http_error status=%s body=%s",
                resp.status_code,
                (resp.text or "")[:500],
            )
            raise GrokUnavailableError(f"Grok HTTP {resp.status_code}")

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            logger.warning("grok_ats_empty_choices response_keys=%s", list(data.keys()))
            raise GrokUnavailableError("Grok empty choices")

        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise GrokUnavailableError("Grok empty content")
        logger.info(
            "ats.provider.completed",
            extra={
                "provider": "xai",
                "model": self._model,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )
        return content.strip()


class GroqAtsClient:
    """Groq OpenAI-compatible client for ATS semantic enrichment."""

    def __init__(self) -> None:
        s = get_settings()
        self._api_key = (s.groq_ats_api_key or "").strip()
        self._base = (s.groq_ats_api_base or "https://api.groq.com/openai/v1").rstrip("/")
        self._model = s.groq_ats_model or "llama-3.3-70b-versatile"
        self._timeout = float(s.groq_ats_timeout_seconds or 10.0)

    def is_configured(self) -> bool:
        return bool(self._api_key)

    @retry(
        reraise=True,
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)),
    )
    def chat_json_system_user(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.15,
    ) -> str:
        if not self.is_configured():
            raise GrokUnavailableError("GROQ_API_KEY_ATS not set")

        url = f"{self._base}/chat/completions"
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        payload: dict[str, Any] = {
            "model": self._model,
            "temperature": temperature,
            "messages": messages,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        logger.info(
            "groq_ats_request model=%s timeout=%s messages=%s",
            self._model,
            self._timeout,
            json.dumps(_redact_messages_for_log(messages)),
        )

        t0 = time.monotonic()
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, headers=headers, json=payload)

        if resp.status_code >= 400:
            logger.warning(
                "groq_ats_http_error status=%s body=%s",
                resp.status_code,
                (resp.text or "")[:500],
            )
            raise GrokUnavailableError(f"Groq HTTP {resp.status_code}")

        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            raise GrokUnavailableError("Groq empty choices")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise GrokUnavailableError("Groq empty content")
        logger.info(
            "ats.provider.completed",
            extra={
                "provider": "groq",
                "model": self._model,
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )
        return content.strip()
