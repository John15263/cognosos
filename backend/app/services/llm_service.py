from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from backend.app.core.config import get_settings
from backend.app.providers.llm_anthropic import AnthropicLLMProvider
from backend.app.providers.llm_base import LLMProvider
from backend.app.providers.llm_gemini import GeminiLLMProvider
from backend.app.providers.llm_mock import MockLLMProvider
from backend.app.providers.llm_openai import OpenAILLMProvider
from backend.app.providers.llm_remote_stub import RemoteLLMStubProvider

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _is_local_url(url: str | None) -> bool:
    """Only loopback hosts are guaranteed to keep data on this machine. Anything else
    — including LAN/mDNS names like ``*.local`` and the unspecified address
    ``0.0.0.0`` — may be another host, so it requires the ALLOW_REMOTE_LLM opt-in."""
    if not url:
        return False
    host = (urlparse(url).hostname or "").lower()
    return host in _LOCAL_HOSTS


def _require_remote_enabled(provider: str) -> None:
    if not get_settings().allow_remote_llm:
        raise RuntimeError(
            f"{provider} LLM calls are disabled. Set ALLOW_REMOTE_LLM=true to enable them."
        )


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider

    if provider == "mock":
        return MockLLMProvider()

    if provider == "gemini":
        _require_remote_enabled("Gemini")
        return GeminiLLMProvider(
            api_key=settings.gemini_api_key or "",
            model_name=settings.gemini_llm_model,
        )

    if provider == "openai":
        # Local OpenAI-compatible endpoints (Ollama, LM Studio, ...) send nothing
        # off-device, so they don't require the remote opt-in; hosted ones do.
        if not _is_local_url(settings.openai_base_url):
            _require_remote_enabled("OpenAI")
        return OpenAILLMProvider(
            api_key=settings.openai_api_key or "",
            model_name=settings.openai_llm_model,
            base_url=settings.openai_base_url,
        )

    if provider == "anthropic":
        _require_remote_enabled("Anthropic")
        return AnthropicLLMProvider(
            api_key=settings.anthropic_api_key or "",
            model_name=settings.anthropic_llm_model,
        )

    return RemoteLLMStubProvider(settings.allow_remote_llm)
