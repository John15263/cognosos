from __future__ import annotations

from typing import Any

from backend.app.providers.llm_json_provider import JSONChatLLMProvider

_SYSTEM = "Return only valid JSON matching the requested shape. No markdown, no prose, no code fences."


class AnthropicLLMProvider(JSONChatLLMProvider):
    """Anthropic (Claude) chat provider."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "claude-opus-4-8",
        client: Any | None = None,
    ) -> None:
        self.model_name = model_name

        if client is not None:
            self._client = client
            return

        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for Anthropic LLM calls.")

        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic is not installed. Install with `pip install -e '.[anthropic]'`."
            ) from exc

        self._client = anthropic.Anthropic(api_key=api_key)

    def _complete(self, prompt: str) -> str:
        # Adaptive thinking improves extraction quality on nuanced entries; max_tokens is
        # set well above the JSON payload so reasoning never crowds out the answer.
        message = self._client.messages.create(
            model=self.model_name,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text
            for block in message.content
            if getattr(block, "type", None) == "text"
        )
