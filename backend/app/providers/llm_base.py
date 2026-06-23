from __future__ import annotations

from abc import ABC, abstractmethod

from backend.app.models.schemas import ExtractorOutput, TriggerDecision


class LLMProvider(ABC):
    @abstractmethod
    def extract_cards(self, raw_text: str) -> ExtractorOutput:
        raise NotImplementedError

    @abstractmethod
    def judge_triggers(self, candidates: list[TriggerDecision]) -> list[TriggerDecision]:
        raise NotImplementedError

