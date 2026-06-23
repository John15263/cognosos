from __future__ import annotations

from backend.app.models.schemas import ExtractorOutput, TriggerDecision
from backend.app.providers.llm_base import LLMProvider


class RemoteLLMStubProvider(LLMProvider):
    def __init__(self, allow_remote_llm: bool) -> None:
        if not allow_remote_llm:
            raise RuntimeError("Remote LLM use is disabled. Set ALLOW_REMOTE_LLM=true to enable a remote provider.")

    def extract_cards(self, raw_text: str) -> ExtractorOutput:
        raise NotImplementedError("Remote LLM provider is intentionally a stub in the MVP.")

    def judge_triggers(self, candidates: list[TriggerDecision]) -> list[TriggerDecision]:
        raise NotImplementedError("Remote LLM provider is intentionally a stub in the MVP.")

