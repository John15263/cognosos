import json
from types import SimpleNamespace

import pytest

from backend.app.models.enums import TriggerModuleType
from backend.app.models.schemas import TriggerDecision
from backend.app.providers.llm_anthropic import AnthropicLLMProvider
from backend.app.providers.llm_openai import OpenAILLMProvider

EXTRACTOR_PAYLOAD = {
    "cards": [
        {
            "module_type": "decision",
            "title": "Decision",
            "summary": "我决定明天先做最小 demo",
            "content": "我决定明天先做最小 demo",
            "content_for_embedding": "decision: 我决定明天先做最小 demo",
            "emotion_score": 4,
            "importance_score": 8,
            "urgency_score": 7,
            "status": "open",
            "privacy_level": "private",
            "metadata_json": {
                "people": [],
                "topics": ["demo"],
                "next_actions": [],
                "predictions": [],
                "expected_outcome": None,
                "return_action": None,
                "check_reason": None,
            },
        }
    ]
}

JUDGE_PAYLOAD = {
    "decisions": [
        {
            "triggered": True,
            "triggered_module": "decision",
            "confidence": 0.8,
            "reason": "Important decision detected.",
            "evidence_card_ids": [],
            "intervention_level": 2,
            "next_question": "什么时候回来检查？",
        }
    ]
}


class FakeOpenAICompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        message = SimpleNamespace(content=self.content)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def _fake_openai_client(content: str) -> SimpleNamespace:
    completions = FakeOpenAICompletions(content)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


class FakeAnthropicMessages:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        # Mimic Claude returning an (optional) thinking block plus a text block.
        thinking = SimpleNamespace(type="thinking", thinking="")
        text_block = SimpleNamespace(type="text", text=self.text)
        return SimpleNamespace(content=[thinking, text_block])


def _fake_anthropic_client(text: str) -> SimpleNamespace:
    return SimpleNamespace(messages=FakeAnthropicMessages(text))


def test_openai_provider_validates_extractor_json():
    client = _fake_openai_client(json.dumps(EXTRACTOR_PAYLOAD, ensure_ascii=False))
    provider = OpenAILLMProvider(api_key="", model_name="gpt-4o-mini", client=client)

    output = provider.extract_cards("我决定明天先做最小 demo")

    assert output.cards[0].module_type == "decision"
    call = client.chat.completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["model"] == "gpt-4o-mini"


def test_openai_provider_strips_code_fence_and_judges():
    fenced = "```json\n" + json.dumps(JUDGE_PAYLOAD, ensure_ascii=False) + "\n```"
    client = _fake_openai_client(fenced)
    provider = OpenAILLMProvider(api_key="", model_name="gpt-4o-mini", client=client)

    decisions = provider.judge_triggers(
        [TriggerDecision(triggered=True, triggered_module=TriggerModuleType.decision)]
    )

    assert decisions[0].triggered_module == TriggerModuleType.decision


def test_anthropic_provider_validates_extractor_json():
    client = _fake_anthropic_client(json.dumps(EXTRACTOR_PAYLOAD, ensure_ascii=False))
    provider = AnthropicLLMProvider(api_key="", model_name="claude-opus-4-8", client=client)

    output = provider.extract_cards("我决定明天先做最小 demo")

    assert output.cards[0].module_type == "decision"
    call = client.messages.calls[0]
    assert call["model"] == "claude-opus-4-8"
    assert call["thinking"] == {"type": "adaptive"}


def test_judge_triggers_returns_empty_without_candidates():
    client = _fake_openai_client("should-not-be-called")
    provider = OpenAILLMProvider(api_key="", model_name="gpt-4o-mini", client=client)

    assert provider.judge_triggers([]) == []
    assert client.chat.completions.calls == []


def test_invalid_json_retries_then_raises():
    client = _fake_openai_client("not json at all")
    provider = OpenAILLMProvider(api_key="", model_name="gpt-4o-mini", client=client)

    with pytest.raises(ValueError, match="invalid JSON"):
        provider.extract_cards("hello")

    # Two attempts: initial + one retry.
    assert len(client.chat.completions.calls) == 2
