from __future__ import annotations

from functools import lru_cache

from backend.app.core.config import get_settings
from backend.app.providers.llm_base import LLMProvider
from backend.app.providers.llm_gemini import GeminiLLMProvider
from backend.app.providers.llm_mock import MockLLMProvider
from backend.app.providers.llm_remote_stub import RemoteLLMStubProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "mock":
        return MockLLMProvider()
    if settings.llm_provider == "gemini":
        if not settings.allow_remote_llm:
            raise RuntimeError("Gemini LLM calls are disabled. Set ALLOW_REMOTE_LLM=true to enable them.")
        return GeminiLLMProvider(
            api_key=settings.gemini_api_key or "",
            model_name=settings.gemini_llm_model,
        )
    return RemoteLLMStubProvider(settings.allow_remote_llm)
