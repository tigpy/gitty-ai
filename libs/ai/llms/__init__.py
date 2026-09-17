from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseLLM(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        pass

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str = None, options: Dict[str, Any] = None) -> str:
        pass

class MockLLM(BaseLLM):
    def __init__(self, provider: str = "mock", model: str = "mock-model"):
        self._provider = provider
        self._model = model

    @property
    def provider_name(self) -> str:
        return self._provider

    @property
    def model_name(self) -> str:
        return self._model

    def generate(self, prompt: str, system_prompt: str = None, options: Dict[str, Any] = None) -> str:
        return f"Mock response from {self._provider} ({self._model}) for query: {prompt[:30]}..."

def get_llm_provider(provider_name: str, model_name: str) -> BaseLLM:
    provider_name_lower = provider_name.lower()
    if provider_name_lower == "ollama":
        from .ollama import OllamaProvider
        return OllamaProvider(model_name=model_name)
    elif provider_name_lower == "openai":
        from .openai import OpenAICompatibleProvider
        return OpenAICompatibleProvider(model_name=model_name)
    elif provider_name_lower == "claude":
        from .claude import ClaudeProvider
        return ClaudeProvider(model_name=model_name)
    elif provider_name_lower == "gemini":
        from .gemini import GeminiProvider
        return GeminiProvider(model_name=model_name)
    elif provider_name_lower == "mock":
        return MockLLM(provider=provider_name, model=model_name)
    else:
        raise ValueError(
            f"Unsupported LLM provider: '{provider_name}'. "
            f"Valid options are: ollama, openai, claude, gemini, mock. "
            f"Check the LLM_PROVIDER setting in your .env file."
        )
