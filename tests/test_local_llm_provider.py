"""Focused tests for the Phase-1 local LLM provider layer.

All HTTP calls are mocked — the Qwen model server does NOT need to be running.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

# ── imports under test ────────────────────────────────────────────────────────
from libs.ai.llms import (
    BaseLLM,
    MockLLM,
    OllamaProvider,
    OpenAICompatibleProvider,
    LocalLlamaCppProvider,
    get_llm_provider,
)
from libs.config import get_settings, reset_settings_cache


# ─────────────────────────────────────────────────────────────────────────────
# 1. BaseLLM is abstract
# ─────────────────────────────────────────────────────────────────────────────

def test_base_llm_is_abstract():
    with pytest.raises(TypeError):
        BaseLLM()  # type: ignore[abstract]


# ─────────────────────────────────────────────────────────────────────────────
# 2. MockLLM — deterministic, always available
# ─────────────────────────────────────────────────────────────────────────────

def test_mock_llm_default_response():
    llm = MockLLM(model_name="test-model")
    resp = llm.generate("hello world")
    assert "Mock response from test-model" in resp
    assert "hello world" in resp


def test_mock_llm_custom_response():
    llm = MockLLM(response="fixed answer")
    assert llm.generate("anything") == "fixed answer"


def test_mock_llm_is_available():
    assert MockLLM().is_available() is True


def test_mock_llm_provider_name():
    assert MockLLM().provider_name == "mock"


# ─────────────────────────────────────────────────────────────────────────────
# 3. OllamaProvider
# ─────────────────────────────────────────────────────────────────────────────

@patch("httpx.post")
def test_ollama_generate_success(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"response": "ollama answer"}),
    )
    p = OllamaProvider(model_name="llama3", base_url="http://localhost:11434")
    assert p.generate("What is Python?") == "ollama answer"
    mock_post.assert_called_once_with(
        "http://localhost:11434/api/generate",
        json={"model": "llama3", "prompt": "What is Python?", "stream": False},
        timeout=30.0,
    )


@patch("httpx.post")
def test_ollama_generate_with_system_prompt(mock_post):
    mock_post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"response": "ok"}),
    )
    p = OllamaProvider()
    p.generate("Q", system_prompt="You are a guide")
    payload = mock_post.call_args[1]["json"]
    assert payload["system"] == "You are a guide"


@patch("httpx.post")
def test_ollama_generate_http_error(mock_post):
    mock_post.return_value = MagicMock(status_code=500, text="internal error")
    p = OllamaProvider()
    with pytest.raises(RuntimeError, match="Ollama generation failed"):
        p.generate("Q")


@patch("httpx.post")
def test_ollama_generate_connection_error(mock_post):
    mock_post.side_effect = Exception("Connection refused")
    p = OllamaProvider()
    with pytest.raises(RuntimeError, match="Ollama generation failed"):
        p.generate("Q")


@patch("httpx.get")
def test_ollama_is_available_true(mock_get):
    mock_get.return_value = MagicMock(status_code=200)
    assert OllamaProvider().is_available() is True


@patch("httpx.get")
def test_ollama_is_available_false(mock_get):
    mock_get.side_effect = Exception("refused")
    assert OllamaProvider().is_available() is False


# ─────────────────────────────────────────────────────────────────────────────
# 4. OpenAICompatibleProvider
# ─────────────────────────────────────────────────────────────────────────────

@patch("libs.ai.llms.openai.OpenAICompatibleProvider._client")
def test_openai_generate_success(mock_client_method):
    client = MagicMock()
    mock_client_method.return_value = client
    choice = MagicMock()
    choice.message.content = "openai answer"
    client.chat.completions.create.return_value = MagicMock(choices=[choice])

    p = OpenAICompatibleProvider(model_name="gpt-4o", api_key="sk-test")
    assert p.generate("Q") == "openai answer"


@patch("libs.ai.llms.openai.OpenAICompatibleProvider._client")
def test_openai_generate_error(mock_client_method):
    client = MagicMock()
    mock_client_method.return_value = client
    client.chat.completions.create.side_effect = Exception("API error")

    p = OpenAICompatibleProvider(model_name="gpt-4o", api_key="sk-bad")
    with pytest.raises(RuntimeError, match="OpenAI generation failed"):
        p.generate("Q")


@patch("libs.ai.llms.openai.OpenAICompatibleProvider._client")
def test_openai_passes_options(mock_client_method):
    client = MagicMock()
    mock_client_method.return_value = client
    choice = MagicMock()
    choice.message.content = "ok"
    client.chat.completions.create.return_value = MagicMock(choices=[choice])

    p = OpenAICompatibleProvider(model_name="gpt-4o", api_key="sk-test")
    p.generate("Q", system_prompt="sys", options={"temperature": 0.5})

    call_kwargs = client.chat.completions.create.call_args[1]
    assert call_kwargs["temperature"] == 0.5
    messages = call_kwargs["messages"]
    assert messages[0] == {"role": "system", "content": "sys"}


# ─────────────────────────────────────────────────────────────────────────────
# 5. LocalLlamaCppProvider — the primary new provider
# ─────────────────────────────────────────────────────────────────────────────

def _llamacpp_ok_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return resp


@patch("httpx.post")
def test_llamacpp_generate_success(mock_post):
    mock_post.return_value = _llamacpp_ok_response("qwen answer")
    p = LocalLlamaCppProvider(
        model_name="qwen3.5", base_url="http://127.0.0.1:8080", timeout=30.0
    )
    result = p.generate("Explain imports")
    assert result == "qwen answer"
    mock_post.assert_called_once()
    payload = mock_post.call_args[1]["json"]
    assert payload["model"] == "qwen3.5"
    assert payload["stream"] is False
    assert payload["messages"][-1]["role"] == "user"


@patch("httpx.post")
def test_llamacpp_generate_with_system_prompt(mock_post):
    mock_post.return_value = _llamacpp_ok_response("ok")
    p = LocalLlamaCppProvider(base_url="http://127.0.0.1:8080")
    p.generate("Q", system_prompt="You are a code reviewer")
    payload = mock_post.call_args[1]["json"]
    assert payload["messages"][0] == {"role": "system", "content": "You are a code reviewer"}
    assert payload["messages"][1]["role"] == "user"


@patch("httpx.post")
def test_llamacpp_generate_http_error(mock_post):
    resp = MagicMock()
    resp.status_code = 503
    resp.text = "service unavailable"
    mock_post.return_value = resp
    p = LocalLlamaCppProvider(base_url="http://127.0.0.1:8080")
    with pytest.raises(RuntimeError, match="llama.cpp returned HTTP 503"):
        p.generate("Q")


@patch("httpx.post")
def test_llamacpp_generate_connection_refused(mock_post):
    mock_post.side_effect = Exception("Connection refused")
    p = LocalLlamaCppProvider(base_url="http://127.0.0.1:8080")
    with pytest.raises(RuntimeError, match="Local llama.cpp inference failed"):
        p.generate("Q")


@patch("httpx.get")
def test_llamacpp_is_available_true(mock_get):
    mock_get.return_value = MagicMock(status_code=200)
    p = LocalLlamaCppProvider(base_url="http://127.0.0.1:8080")
    assert p.is_available() is True
    mock_get.assert_called_once_with("http://127.0.0.1:8080/health", timeout=3.0)


@patch("httpx.get")
def test_llamacpp_is_available_false_server_down(mock_get):
    mock_get.side_effect = Exception("refused")
    p = LocalLlamaCppProvider(base_url="http://127.0.0.1:8080")
    assert p.is_available() is False


@patch("httpx.get")
def test_llamacpp_is_available_false_non_200(mock_get):
    mock_get.return_value = MagicMock(status_code=404)
    p = LocalLlamaCppProvider(base_url="http://127.0.0.1:8080")
    assert p.is_available() is False


def test_llamacpp_reads_env_vars(monkeypatch):
    monkeypatch.setenv("GITTY_LLM_BASE_URL", "http://192.168.1.10:9090")
    monkeypatch.setenv("GITTY_LLM_MODEL", "custom-qwen")
    monkeypatch.setenv("GITTY_LLM_TIMEOUT", "60")
    p = LocalLlamaCppProvider()
    assert p.base_url == "http://192.168.1.10:9090"
    assert p.model_name == "custom-qwen"
    assert p.timeout == 60.0


def test_llamacpp_explicit_args_override_env(monkeypatch):
    monkeypatch.setenv("GITTY_LLM_BASE_URL", "http://env-host:8080")
    p = LocalLlamaCppProvider(base_url="http://explicit:9000", model_name="override")
    assert p.base_url == "http://explicit:9000"
    assert p.model_name == "override"


# ─────────────────────────────────────────────────────────────────────────────
# 6. get_llm_provider() factory
# ─────────────────────────────────────────────────────────────────────────────

def test_factory_mock():
    p = get_llm_provider("mock", "test-model")
    assert isinstance(p, MockLLM)
    assert p.model_name == "test-model"


def test_factory_mock_case_insensitive():
    p = get_llm_provider("MOCK", "m")
    assert isinstance(p, MockLLM)


def test_factory_unknown_falls_back_to_mock():
    p = get_llm_provider("nonexistent_provider", "m")
    assert isinstance(p, MockLLM)


def test_factory_ollama(monkeypatch):
    # Ensure GITTY_LLM_ENABLED is off so the factory doesn't promote to llamacpp
    reset_settings_cache()
    monkeypatch.setenv("GITTY_LLM_ENABLED", "false")
    reset_settings_cache()
    p = get_llm_provider("ollama", "llama3")
    assert isinstance(p, OllamaProvider)
    assert p.model_name == "llama3"


def test_factory_openai(monkeypatch):
    reset_settings_cache()
    monkeypatch.setenv("GITTY_LLM_ENABLED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    reset_settings_cache()
    p = get_llm_provider("openai", "gpt-4o")
    assert isinstance(p, OpenAICompatibleProvider)
    assert p.model_name == "gpt-4o"
    assert p._api_key == "sk-test-key"


def test_factory_llamacpp_explicit(monkeypatch):
    reset_settings_cache()
    monkeypatch.setenv("GITTY_LLM_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("GITTY_LLM_MODEL", "qwen3.5-9b-q4")
    monkeypatch.setenv("GITTY_LLM_TIMEOUT", "90")
    reset_settings_cache()
    p = get_llm_provider("llamacpp", "qwen3.5-9b-q4")
    assert isinstance(p, LocalLlamaCppProvider)
    assert p.model_name == "qwen3.5-9b-q4"
    assert p.base_url == "http://127.0.0.1:8080"
    assert p.timeout == 90.0


# ─────────────────────────────────────────────────────────────────────────────
# 7. LLM disabled — GITTY_LLM_ENABLED=false keeps existing provider
# ─────────────────────────────────────────────────────────────────────────────

def test_llm_disabled_does_not_promote_to_llamacpp(monkeypatch):
    """When GITTY_LLM_ENABLED is False, ollama request must stay ollama."""
    reset_settings_cache()
    monkeypatch.setenv("GITTY_LLM_ENABLED", "false")
    reset_settings_cache()
    p = get_llm_provider("ollama", "llama3")
    assert isinstance(p, OllamaProvider)
    reset_settings_cache()


def test_llm_enabled_promotes_ollama_to_llamacpp(monkeypatch):
    """When GITTY_LLM_ENABLED is True, the factory upgrades ollama -> llamacpp."""
    reset_settings_cache()
    monkeypatch.setenv("GITTY_LLM_ENABLED", "true")
    monkeypatch.setenv("GITTY_LLM_BASE_URL", "http://127.0.0.1:8080")
    reset_settings_cache()
    p = get_llm_provider("ollama", "llama3")
    assert isinstance(p, LocalLlamaCppProvider)
    reset_settings_cache()


def test_llm_enabled_promotes_mock_to_llamacpp(monkeypatch):
    """When GITTY_LLM_ENABLED is True, mock is also promoted."""
    reset_settings_cache()
    monkeypatch.setenv("GITTY_LLM_ENABLED", "true")
    monkeypatch.setenv("GITTY_LLM_BASE_URL", "http://127.0.0.1:8080")
    reset_settings_cache()
    p = get_llm_provider("mock", "any")
    assert isinstance(p, LocalLlamaCppProvider)
    reset_settings_cache()


def test_llm_enabled_does_not_override_explicit_openai(monkeypatch):
    """Explicit openai must not be overridden even when GITTY_LLM_ENABLED=true."""
    reset_settings_cache()
    monkeypatch.setenv("GITTY_LLM_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-x")
    reset_settings_cache()
    p = get_llm_provider("openai", "gpt-4o")
    assert isinstance(p, OpenAICompatibleProvider)
    reset_settings_cache()


# ─────────────────────────────────────────────────────────────────────────────
# 8. Existing test_llm_providers.py shape — verify factory returns expected types
#    (duplicates the old test structure to confirm backward compat)
# ─────────────────────────────────────────────────────────────────────────────

def test_get_llm_provider_mock_compat():
    """Matches the shape expected by the pre-existing test_llm_providers.py."""
    reset_settings_cache()
    provider = get_llm_provider("mock", "mock-model")
    assert provider.provider_name == "mock"
    assert provider.model_name == "mock-model"
    resp = provider.generate("hello")
    assert "Mock response from mock-model" in resp
