"""Local llama.cpp LLM provider for Gitty AI.

Connects to a llama.cpp server running in OpenAI-compatibility mode:

    llama-server \\
        --model "D:\\Evidentia-Models\\Qwen3.5-9B-Q4_K_M\\Qwen3.5-9B-Q4_K_M.gguf" \\
        --host 127.0.0.1 \\
        --port 8080 \\
        --ctx-size 8192 \\
        --n-predict 1024

The server exposes /v1/chat/completions and /health, which this provider
calls using plain httpx (no openai package required).

Configuration (all via environment variables — nothing is hard-coded):

    GITTY_LLM_ENABLED   = "true"            # set to "false" to disable
    GITTY_LLM_BASE_URL  = "http://127.0.0.1:8080"
    GITTY_LLM_MODEL     = "qwen3.5-9b-q4"  # label only, passed as model= field
    GITTY_LLM_TIMEOUT   = "120"             # seconds

The GGUF file path is NEVER stored here.  The user starts the llama.cpp
server independently, pointing it at the model on disk.

When the server is unavailable this provider raises RuntimeError with a
user-friendly message; ChatService already catches that and returns a
graceful UI string instead of an HTTP 500.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Generator, Optional

from .base import BaseLLM

_DEFAULT_BASE_URL = "http://127.0.0.1:8080"
_DEFAULT_MODEL = "local-qwen"
_DEFAULT_TIMEOUT = 120.0


class LocalLlamaCppProvider(BaseLLM):
    """Calls a llama.cpp /v1/chat/completions endpoint with httpx.

    Supports both regular (non-streaming) and streaming responses.
    """

    provider_name: str = "llamacpp"

    def __init__(
        self,
        model_name: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.model_name = model_name or os.environ.get("GITTY_LLM_MODEL", _DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get("GITTY_LLM_BASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout or float(os.environ.get("GITTY_LLM_TIMEOUT", str(_DEFAULT_TIMEOUT)))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send *prompt* to the llama.cpp server and return the full reply."""
        return "".join(self._generate_chunks(prompt, system_prompt, options, stream=False))

    def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Generator[str, None, None]:
        """Yield response tokens as they arrive (SSE stream from llama.cpp)."""
        yield from self._generate_chunks(prompt, system_prompt, options, stream=True)

    def is_available(self) -> bool:
        """Return True when the llama.cpp server /health endpoint responds 200."""
        import httpx  # lazy import — no hard dependency at module level

        try:
            resp = httpx.get(f"{self.base_url}/health", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_messages(
        self, prompt: str, system_prompt: Optional[str]
    ) -> list:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _generate_chunks(
        self,
        prompt: str,
        system_prompt: Optional[str],
        options: Optional[Dict[str, Any]],
        stream: bool,
    ) -> Generator[str, None, None]:
        import httpx  # lazy import

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": self._build_messages(prompt, system_prompt),
            "stream": stream,
        }
        if options:
            for k, v in options.items():
                if k not in ("stream", "model"):
                    payload[k] = v

        endpoint = f"{self.base_url}/v1/chat/completions"

        try:
            if not stream:
                resp = httpx.post(endpoint, json=payload, timeout=self.timeout)
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"llama.cpp returned HTTP {resp.status_code}: {resp.text[:300]}"
                    )
                data = resp.json()
                yield data["choices"][0]["message"]["content"]
            else:
                with httpx.stream("POST", endpoint, json=payload, timeout=self.timeout) as resp:
                    if resp.status_code != 200:
                        raise RuntimeError(
                            f"llama.cpp returned HTTP {resp.status_code}"
                        )
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        payload_str = line[6:]
                        if payload_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(payload_str)
                            delta = chunk["choices"][0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                yield token
                        except (KeyError, json.JSONDecodeError):
                            continue
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Local llama.cpp inference failed — is the server running at "
                f"{self.base_url}?  Details: {exc}"
            ) from exc
