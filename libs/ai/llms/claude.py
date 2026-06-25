import anthropic
from typing import Dict, Any, Optional
from libs.config import get_settings
from . import BaseLLM


class ClaudeProvider(BaseLLM):
    """
    LLM provider backed by the Anthropic Claude API.
    Set LLM_PROVIDER=claude and CLAUDE_API_KEY=<key> in your .env to use this.
    Defaults to claude-3-5-haiku-20241022 which is fast and cheap; override with
    LLM_MODEL=claude-opus-4-6 etc.
    """

    def __init__(self, model_name: str, api_key: Optional[str] = None):
        self.settings = get_settings()
        self._model_name = model_name
        self._api_key = api_key or self.settings.CLAUDE_API_KEY
        if not self._api_key:
            raise ValueError(
                "CLAUDE_API_KEY is required when LLM_PROVIDER=claude. "
                "Set it in your .env file."
            )

    @property
    def provider_name(self) -> str:
        return "claude"

    @property
    def model_name(self) -> str:
        return self._model_name

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        client = anthropic.Anthropic(api_key=self._api_key)
        kwargs: Dict[str, Any] = {"max_tokens": 4096}
        if options:
            kwargs.update(options)

        messages = [{"role": "user", "content": prompt}]

        try:
            response = client.messages.create(
                model=self._model_name,
                system=system_prompt or "",
                messages=messages,
                **kwargs,
            )
            return response.content[0].text if response.content else ""
        except Exception as e:
            raise RuntimeError(f"Claude generation failed: {e}") from e
