"""Provider-agnostic LLM client (httpx). Never raises into a request: failures return None."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.config import get_settings

log = logging.getLogger("truthlens.llm")

DEFAULT_MODELS = {
    "anthropic": "claude-haiku-5-5",
    "openai": "gpt-4o-mini",
    "gemini": "gemini-2.0-flash",
    "ollama": "llama3.2",
}


def extract_json(text: str) -> dict[str, Any] | None:
    """Parse the first JSON object found in model output."""
    if not text:
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


class LLMClient:
    """One interface over anthropic | openai | gemini | ollama."""

    def __init__(self) -> None:
        s = get_settings()
        self.provider = s.llm_provider.lower()
        self.model = s.llm_model or DEFAULT_MODELS.get(self.provider, "")
        self.key = s.llm_api_key
        self.ollama_url = s.ollama_url.rstrip("/")
        self.timeout = s.llm_timeout_s

    @property
    def enabled(self) -> bool:
        """True when a provider is selected and has what it needs (key, or a URL for ollama)."""
        if self.provider == "ollama":
            return True
        return self.provider in ("anthropic", "openai", "gemini") and bool(self.key)

    def complete_json(self, system: str, user: str) -> dict[str, Any] | None:
        """Ask for a JSON object. Returns None on any error, timeout or unparsable reply."""
        if not self.enabled:
            return None
        try:
            with httpx.Client(timeout=self.timeout) as c:
                raw = getattr(self, f"_{self.provider}")(c, system, user)
            return extract_json(raw)
        except Exception as exc:  # noqa: BLE001 - must never crash a request
            log.warning("LLM call failed: %s", type(exc).__name__)
            return None

    def _anthropic(self, c: httpx.Client, system: str, user: str) -> str:
        r = c.post("https://api.anthropic.com/v1/messages",
                   headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"},
                   json={"model": self.model, "max_tokens": 700, "system": system, "messages": [{"role": "user", "content": user}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))

    def _openai(self, c: httpx.Client, system: str, user: str) -> str:
        r = c.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {self.key}"},
                   json={"model": self.model, "response_format": {"type": "json_object"}, "temperature": 0.2,
                         "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]

    def _gemini(self, c: httpx.Client, system: str, user: str) -> str:
        r = c.post(f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                   headers={"x-goog-api-key": self.key},
                   json={"systemInstruction": {"parts": [{"text": system}]}, "contents": [{"role": "user", "parts": [{"text": user}]}],
                         "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _ollama(self, c: httpx.Client, system: str, user: str) -> str:
        r = c.post(f"{self.ollama_url}/api/chat",
                   json={"model": self.model, "stream": False, "format": "json",
                         "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
        r.raise_for_status()
        return r.json()["message"]["content"]


def get_client() -> LLMClient:
    """Fresh client reading current settings."""
    return LLMClient()
