"""Ollama LLM provider — calls the /api/generate endpoint."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseLLM


class OllamaProvider(BaseLLM):
    """Connects to a locally running Ollama instance."""

    provider_name: str = "ollama"

    def __init__(
        self,
        model_name: str = "llama3",
        base_url: str = "http://localhost:11434",
        timeout: float = 30.0,
    ) -> None:
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        import httpx

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt
        if options:
            payload.update(options)

        try:
            resp = httpx.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
        except Exception as exc:
            raise RuntimeError(f"Ollama generation failed: {exc}") from exc

        if resp.status_code != 200:
            raise RuntimeError(
                f"Ollama generation failed: HTTP {resp.status_code} — {resp.text[:200]}"
            )
        try:
            return resp.json()["response"]
        except Exception as exc:
            raise RuntimeError(f"Ollama generation failed: unexpected response shape — {exc}") from exc

    def is_available(self) -> bool:
        """Return True when the Ollama daemon is reachable."""
        import httpx

        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False
