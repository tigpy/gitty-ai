import httpx
from typing import Dict, Any, Optional
from libs.config import get_settings
from . import BaseLLM

class OllamaProvider(BaseLLM):
    def __init__(self, model_name: str, base_url: Optional[str] = None):
        self.settings = get_settings()
        self._model_name = model_name
        self.base_url = base_url or self.settings.OLLAMA_URI

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(self, prompt: str, system_prompt: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> str:
        url = f"{self.base_url.rstrip('/')}/api/generate"
        payload = {
            "model": self._model_name,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt
        if options:
            payload["options"] = options

        try:
            response = httpx.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except Exception as e:
            raise RuntimeError(f"Ollama generation failed: {e}")
