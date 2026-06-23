import pytest

from backend.app.core.config import get_settings
from backend.app.providers.llm_mock import MockLLMProvider
from backend.app.providers.llm_openai import OpenAILLMProvider
from backend.app.services import llm_service


def _reset_caches():
    get_settings.cache_clear()
    llm_service.get_llm_provider.cache_clear()


@pytest.fixture(autouse=True)
def _isolate(monkeypatch):
    # Ensure each test builds settings/provider fresh from its own env.
    _reset_caches()
    yield
    _reset_caches()


def _env(monkeypatch, **values):
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    _reset_caches()


def test_mock_is_default(monkeypatch):
    _env(monkeypatch, LLM_PROVIDER="mock", ALLOW_REMOTE_LLM="false")
    assert isinstance(llm_service.get_llm_provider(), MockLLMProvider)


def test_remote_provider_blocked_without_opt_in(monkeypatch):
    _env(monkeypatch, LLM_PROVIDER="anthropic", ALLOW_REMOTE_LLM="false", ANTHROPIC_API_KEY="x")
    with pytest.raises(RuntimeError, match="Anthropic LLM calls are disabled"):
        llm_service.get_llm_provider()


def test_openai_hosted_blocked_without_opt_in(monkeypatch):
    _env(monkeypatch, LLM_PROVIDER="openai", ALLOW_REMOTE_LLM="false", OPENAI_API_KEY="x")
    with pytest.raises(RuntimeError, match="OpenAI LLM calls are disabled"):
        llm_service.get_llm_provider()


def test_local_openai_compatible_allowed_without_opt_in(monkeypatch):
    # A localhost base_url keeps data on-device, so no remote opt-in is needed.
    _env(
        monkeypatch,
        LLM_PROVIDER="openai",
        ALLOW_REMOTE_LLM="false",
        OPENAI_BASE_URL="http://localhost:11434/v1",
        OPENAI_API_KEY="ollama",
    )
    try:
        provider = llm_service.get_llm_provider()
    except RuntimeError as exc:
        # The privacy gate must NOT block a local endpoint; only a missing optional
        # SDK may (the `openai` package is not a base dependency).
        assert "disabled" not in str(exc)
        assert "not installed" in str(exc)
    else:
        assert isinstance(provider, OpenAILLMProvider)


def test_is_local_url_detection():
    # Loopback only — these stay on the machine.
    assert llm_service._is_local_url("http://127.0.0.1:11434/v1")
    assert llm_service._is_local_url("http://localhost:1234/v1")
    assert llm_service._is_local_url("http://[::1]:1234/v1")
    # LAN / mDNS names and the unspecified address may be another host, so they are
    # NOT treated as local and must require ALLOW_REMOTE_LLM.
    assert not llm_service._is_local_url("http://my-box.local/v1")
    assert not llm_service._is_local_url("http://0.0.0.0:11434/v1")
    assert not llm_service._is_local_url("https://api.openai.com/v1")
    assert not llm_service._is_local_url(None)
