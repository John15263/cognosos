from __future__ import annotations

from typing import Any

from backend.app.providers.llm_json_provider import JSONChatLLMProvider


class OpenAILLMProvider(JSONChatLLMProvider):
    """OpenAI / OpenAI-compatible chat provider.

    Set ``base_url`` to point at any OpenAI-compatible endpoint (Ollama, LM Studio,
    a local gateway, etc.) for a fully local, zero-egress setup. Leave it unset to
    use the hosted OpenAI API.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-mini",
        base_url: str | None = None,
        client: Any | None = None,
    ) -> None:
        self.model_name = model_name

        if client is not None:
            self._client = client
            return

        # Local OpenAI-compatible servers often need no real key; a hosted call does.
        if not api_key and not base_url:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI LLM calls.")

        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "openai is not installed. Install with `pip install -e '.[openai]'`."
            ) from exc

        self._client = OpenAI(api_key=api_key or "not-needed", base_url=base_url)

    def _complete(self, prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""
