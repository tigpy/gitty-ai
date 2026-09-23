"""Mock LLM provider — deterministic, no network, safe for tests."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .base import BaseLLM


class MockLLM(BaseLLM):
    """Deterministic provider that echoes back a canned reply.

    Used in unit tests and when no real provider is configured.
    """

    provider_name: str = "mock"

    def __init__(self, model_name: str = "mock-model", response: str = "") -> None:
        self.model_name = model_name
        self._response = response

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        if self._response:
            return self._response
        return f"Mock response from {self.model_name}: {prompt[:80]}"

    def is_available(self) -> bool:
        return True
