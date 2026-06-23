import json
from types import SimpleNamespace

from backend.app.models.enums import TriggerModuleType
from backend.app.models.schemas import TriggerDecision
from backend.app.providers.embedder_gemini import GeminiEmbedder
from backend.app.providers.llm_gemini import GeminiLLMProvider


class FakeEmbeddingModels:
    def __init__(self) -> None:
        self.calls = []

    def embed_content(self, **kwargs):
        self.calls.append(kwargs)
        dimension = kwargs["config"]["output_dimensionality"]
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1] * dimension)])


class FakeGenerateModels:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(text=self.text)


def test_gemini_embedder_uses_document_and_query_formatting():
    models = FakeEmbeddingModels()
    client = SimpleNamespace(models=models)
    embedder = GeminiEmbedder(api_key="", model_name="gemini-embedding-2", dimension=8, client=client)

    document = embedder.embed("agent 系统", input_type="document")
    query = embedder.embed("agent 系统", input_type="query")

    assert len(document) == 8
    assert len(query) == 8
    assert models.calls[0]["contents"].startswith("title: none | text:")
    assert models.calls[1]["contents"].startswith("task: search result | query:")


def test_gemini_llm_provider_validates_extractor_json():
    payload = {
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
    models = FakeGenerateModels(json.dumps(payload, ensure_ascii=False))
    client = SimpleNamespace(models=models)
    provider = GeminiLLMProvider(api_key="", model_name="gemini-3.5-flash", client=client)

    output = provider.extract_cards("我决定明天先做最小 demo")

    assert output.cards[0].module_type == "decision"
    config = models.calls[0]["config"]
    assert config.response_mime_type == "application/json"
    assert config.response_schema is not None
    assert {getattr(setting.threshold, "value", setting.threshold) for setting in config.safety_settings} == {"BLOCK_NONE"}
    assert "additionalProperties" not in json.dumps(config.response_schema)


def test_gemini_llm_provider_uses_gemini_safe_judge_schema():
    payload = {
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
    models = FakeGenerateModels(json.dumps(payload, ensure_ascii=False))
    client = SimpleNamespace(models=models)
    provider = GeminiLLMProvider(api_key="", model_name="gemini-3.5-flash", client=client)

    output = provider.judge_triggers(
        [
            TriggerDecision(
                triggered=True,
                triggered_module=TriggerModuleType.decision,
                reason="Important decision detected.",
            )
        ]
    )

    assert output[0].triggered_module == TriggerModuleType.decision
    config = models.calls[0]["config"]
    serialized_schema = json.dumps(config.response_schema)
    assert "additionalProperties" not in serialized_schema
    assert "$defs" not in serialized_schema
