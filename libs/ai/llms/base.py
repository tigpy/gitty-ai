"""Base LLM abstraction for Gitty AI.

All concrete providers inherit BaseLLM and must implement ``generate``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseLLM(ABC):
    """Abstract base for every LLM provider used by Gitty AI."""

    #: Short identifier returned in chat metadata (e.g. "ollama", "openai", "llamacpp").
    provider_name: str = "base"
    #: Model identifier forwarded to the inference backend.
    model_name: str = "unknown"

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate a response for *prompt* and return it as a plain string.

        Raises
        ------
        RuntimeError
            When the underlying backend returns an error or is unreachable.
        """

    def is_available(self) -> bool:
        """Return True when the provider backend is reachable.

        Defaults to True; override in providers that need a live health check.
        """
        return True
