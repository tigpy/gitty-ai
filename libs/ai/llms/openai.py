from openai import OpenAI
from typing import Dict, Any, Optional
from libs.config import get_settings
from . import BaseLLM

class OpenAICompatibleProvider(BaseLLM):
    def __init__(self, model_name: str, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.settings = get_settings()
        self._model_name = model_name
        self.api_key = api_key or self.settings.OPENAI_API_KEY
        self.base_url = base_url  # Can be configured for local endpoints like vLLM / LocalAI

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(self, prompt: str, system_prompt: Optional[str] = None, options: Optional[Dict[str, Any]] = None) -> str:
        client = OpenAI(
            api_key=self.api_key or "mock-key-for-tests",
            base_url=self.base_url
        )
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Extra options mappings (e.g. temperature)
        kwargs = {}
        if options:
            for k, v in options.items():
                kwargs[k] = v

        try:
            response = client.chat.completions.create(
                model=self._model_name,
                messages=messages,
                **kwargs
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise RuntimeError(f"OpenAI generation failed: {e}")
