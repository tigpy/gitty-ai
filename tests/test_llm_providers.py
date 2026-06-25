import pytest
from unittest.mock import MagicMock, patch
from libs.ai.llms import get_llm_provider, MockLLM
from libs.ai.llms.ollama import OllamaProvider
from libs.ai.llms.openai import OpenAICompatibleProvider

def test_mock_llm_provider():
    provider = get_llm_provider("mock", "mock-model")
    assert provider.provider_name == "mock"
    assert provider.model_name == "mock-model"
    
    resp = provider.generate("hello")
    assert "Mock response from mock" in resp

@patch("httpx.post")
def test_ollama_provider_success(mock_post):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "Local llama answer"}
    mock_post.return_value = mock_response
    
    provider = OllamaProvider(model_name="llama3", base_url="http://localhost:11434")
    assert provider.provider_name == "ollama"
    assert provider.model_name == "llama3"
    
    res = provider.generate("What is 2+2?", system_prompt="Be a math tutor")
    assert res == "Local llama answer"
    
    # Verify post args
    mock_post.assert_called_once_with(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": "What is 2+2?",
            "stream": False,
            "system": "Be a math tutor"
        },
        timeout=30.0
    )

@patch("httpx.post")
def test_ollama_provider_failure(mock_post):
    mock_post.side_effect = Exception("Connection refused")
    provider = OllamaProvider(model_name="llama3")
    
    with pytest.raises(RuntimeError, match="Ollama generation failed"):
        provider.generate("test")

@patch("libs.ai.llms.openai.OpenAI")
def test_openai_provider_success(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    
    mock_choice = MagicMock()
    mock_choice.message.content = "OpenAI response answer"
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client.chat.completions.create.return_value = mock_response
    
    provider = OpenAICompatibleProvider(model_name="gpt-4o", api_key="sk-test", base_url="http://custom-url")
    assert provider.provider_name == "openai"
    assert provider.model_name == "gpt-4o"
    
    res = provider.generate("hello", system_prompt="be polite", options={"temperature": 0.5})
    assert res == "OpenAI response answer"
    
    mock_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "be polite"},
            {"role": "user", "content": "hello"}
        ],
        temperature=0.5
    )

@patch("libs.ai.llms.openai.OpenAI")
def test_openai_provider_failure(mock_openai_cls):
    mock_client = MagicMock()
    mock_openai_cls.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("API Key Invalid")
    
    provider = OpenAICompatibleProvider(model_name="gpt-4", api_key="invalid")
    with pytest.raises(RuntimeError, match="OpenAI generation failed"):
        provider.generate("test")
