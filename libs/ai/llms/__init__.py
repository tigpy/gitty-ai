"""LLM provider package for Gitty AI.

Exported symbols
----------------
BaseLLM                   – abstract base class
MockLLM                   – deterministic test double
OllamaProvider            – local Ollama daemon
OpenAICompatibleProvider  – OpenAI API or any OpenAI-compat server
LocalLlamaCppProvider     – llama.cpp /v1/chat/completions endpoint

get_llm_provider(provider, model, **kwargs) – factory used by ChatService
"""
from __future__ import annotations

from typing import Any, Optional

from .base import BaseLLM
from .mock import MockLLM
from .ollama import OllamaProvider
from .openai import OpenAICompatibleProvider
from .local_llamacpp import LocalLlamaCppProvider


def get_llm_provider(
    provider: str,
    model: str,
    **kwargs: Any,
) -> BaseLLM:
    """Return a configured LLM provider instance.

    Parameters
    ----------
    provider:
        One of ``"mock"``, ``"ollama"``, ``"openai"``, ``"llamacpp"``.
        Compared case-insensitively.  Unknown values fall back to MockLLM
        with a warning rather than raising, so the application keeps running.
    model:
        Model identifier forwarded to the selected provider.
    **kwargs:
        Extra keyword arguments passed through to the provider constructor
        (e.g. ``base_url``, ``timeout``, ``api_key``).

    Notes
    -----
    When ``GITTY_LLM_ENABLED`` is *True* in ``SystemSettings``, the factory
    prefers ``llamacpp`` over ``ollama`` unless the caller explicitly passes
    a different provider name.  This keeps the existing ``LLM_PROVIDER``
    setting working unchanged while adding the new local path.
    """
    import logging
    log = logging.getLogger("gitty.llm")

    p = (provider or "mock").strip().lower()

    # When the local llama.cpp server is explicitly enabled via GITTY_LLM_ENABLED
    # and the caller has not already requested a specific non-default provider,
    # promote "llamacpp" automatically so existing LLM_PROVIDER=ollama deployments
    # keep working while new local-LLM deployments opt in via the env var alone.
    if p in ("ollama", "mock"):
        try:
            from libs.config import get_settings as _gs
            _s = _gs()
            if getattr(_s, "GITTY_LLM_ENABLED", False):
                p = "llamacpp"
        except Exception:
            pass

    if p == "llamacpp":
        from libs.config import get_settings
        s = get_settings()
        base_url = kwargs.pop("base_url", s.GITTY_LLM_BASE_URL)
        timeout = kwargs.pop("timeout", s.GITTY_LLM_TIMEOUT)
        return LocalLlamaCppProvider(
            model_name=model or s.GITTY_LLM_MODEL,
            base_url=base_url,
            timeout=timeout,
            **kwargs,
        )

    if p == "ollama":
        from libs.config import get_settings
        s = get_settings()
        base_url = kwargs.pop("base_url", s.OLLAMA_URI)
        timeout = kwargs.pop("timeout", 30.0)
        return OllamaProvider(model_name=model, base_url=base_url, timeout=timeout, **kwargs)

    if p == "openai":
        from libs.config import get_settings
        s = get_settings()
        api_key = kwargs.pop("api_key", s.OPENAI_API_KEY or "sk-no-key")
        base_url = kwargs.pop("base_url", None)
        timeout = kwargs.pop("timeout", 30.0)
        return OpenAICompatibleProvider(
            model_name=model,
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            **kwargs,
        )

    if p == "mock":
        response = kwargs.pop("response", "")
        return MockLLM(model_name=model, response=response)

    # Unknown provider — degrade gracefully, never crash the application.
    log.warning(
        "Unknown LLM provider %r — falling back to MockLLM.  "
        "Set LLM_PROVIDER to one of: mock, ollama, openai, llamacpp.",
        provider,
    )
    return MockLLM(model_name=model)


__all__ = [
    "BaseLLM",
    "MockLLM",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "LocalLlamaCppProvider",
    "get_llm_provider",
]
