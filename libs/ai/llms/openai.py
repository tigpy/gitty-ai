"""OpenAI-compatible LLM provider.

Works with the real OpenAI API and with any server that speaks the
OpenAI chat-completions protocol (vLLM, llama.cpp --server, LM Studio, …).
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseLLM

# Import OpenAI at module level so tests can patch 'libs.ai.llms.openai.OpenAI'.
# We guard the import so the application still starts when the package is absent.
try:
    from openai import OpenAI  # type: ignore[import]
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore[assignment,misc]


class OpenAICompatibleProvider(BaseLLM):
    """Calls the OpenAI chat/completions endpoint (or a compatible local clone)."""

    provider_name: str = "openai"

    def __init__(
        self,
        model_name: str = "gpt-4o",
        api_key: str = "sk-no-key",
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ) -> None:
        self.model_name = model_name
        self._api_key = api_key
        self._base_url = base_url
        self.timeout = timeout

    def _client(self):
        """Return a configured OpenAI client (or compatible clone)."""
        if OpenAI is None:  # pragma: no cover
            raise RuntimeError(
                "The 'openai' package is not installed. "
                "Run: pip install openai"
            )
        kwargs: Dict[str, Any] = {"api_key": self._api_key}
        if self._base_url:
            kwargs["base_url"] = self._base_url
        return OpenAI(**kwargs)

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        options = options or {}
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            completion = self._client().chat.completions.create(
                model=self.model_name,
                messages=messages,
                **{k: v for k, v in options.items() if k != "stream"},
            )
            return completion.choices[0].message.content
        except Exception as exc:
            raise RuntimeError(f"OpenAI generation failed: {exc}") from exc

    def is_available(self) -> bool:
        """Best-effort reachability check — does not consume tokens."""
        try:
            import httpx

            url = (self._base_url or "https://api.openai.com").rstrip("/")
            # llama.cpp exposes /health; OpenAI has no public ping endpoint, so
            # we fall back to a 401 being "reachable" for the real API.
            resp = httpx.get(f"{url}/health", timeout=3.0)
            return resp.status_code in (200, 401, 404)
        except Exception:
            return False
