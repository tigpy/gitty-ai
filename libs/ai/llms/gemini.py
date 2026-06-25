from typing import Dict, Any, Optional
from libs.config import get_settings
from . import BaseLLM


class GeminiProvider(BaseLLM):
    """
    LLM provider backed by Google Gemini via the google-generativeai SDK.
    Set LLM_PROVIDER=gemini and GEMINI_API_KEY=<key> in your .env to use this.
    Default model: gemini-1.5-flash (fast, free tier available).
    """

    def __init__(self, model_name: str, api_key: Optional[str] = None):
        self.settings = get_settings()
        self._model_name = model_name
        self._api_key = api_key or self.settings.GEMINI_API_KEY
        if not self._api_key:
            raise ValueError(
                "GEMINI_API_KEY is required when LLM_PROVIDER=gemini. "
                "Set it in your .env file."
            )

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise RuntimeError(
                "google-generativeai is not installed. "
                "Run: pip install google-generativeai"
            ) from e

        genai.configure(api_key=self._api_key)

        generation_config = {}
        if options:
            generation_config.update(options)

        model = genai.GenerativeModel(
            model_name=self._model_name,
            system_instruction=system_prompt,
            generation_config=generation_config or None,
        )
        try:
            response = model.generate_content(prompt)
            return response.text or ""
        except Exception as e:
            raise RuntimeError(f"Gemini generation failed: {e}") from e
