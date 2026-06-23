from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from backend.app.models.enums import CardModuleType, CardStatus, PrivacyLevel
from backend.app.models.schemas import ExtractorCard, ExtractorOutput, TriggerDecision
from backend.app.providers.llm_base import LLMProvider


DECISION_WORDS = ("决定", "要不要", "是否", "选择", "放弃", "开始", "停止", "commit", "choose", "decide")
GRATITUDE_WORDS = ("感激", "感谢", "谢谢", "帮了我", "支持了我", "grateful", "thank")
FUTURE_SELF_WORDS = ("未来的我", "明天的我", "90 天", "90天", "五年后", "future self")
STUCK_WORDS = ("卡住", "不知道怎么开始", "拖延", "无从下手", "stuck", "procrastinating", "don't know where to start")
EMOTION_WORDS = ("焦虑", "难受", "烦", "崩溃", "害怕", "压力", "乱", "overwhelmed", "anxious")
AVSI_WORDS = ("理解", "搞懂", "研究", "概念", "原理", "机制", "框架", "pgvector", "langgraph", "agent", "rag", "embedding", "postgres")
TASK_WORDS = ("待办", "任务", "todo", "下一步", "今天要", "明天要")
TECH_TOPIC_RE = re.compile(r"[A-Za-z][A-Za-z0-9_+#.-]{2,}")
PERSON_RE = re.compile(r"(?:感谢|感激|谢谢)\s*([A-Za-z\u4e00-\u9fff]{1,12})")


@dataclass(frozen=True)
class Classification:
    module_type: CardModuleType
    title: str
    emotion_score: int | None = None
    importance_score: int | None = None
    urgency_score: int | None = None


class MockLLMProvider(LLMProvider):
    def extract_cards(self, raw_text: str) -> ExtractorOutput:
        cards = [self._card_from_segment(segment) for segment in self._segments(raw_text)]
        if not cards:
            cards = [self._card_from_segment(raw_text)]
        return ExtractorOutput(cards=cards)

    def judge_triggers(self, candidates: list[TriggerDecision]) -> list[TriggerDecision]:
        return candidates

    def _segments(self, raw_text: str) -> list[str]:
        chunks = [chunk.strip() for chunk in re.split(r"[。！？!?；;\n]+", raw_text) if chunk.strip()]
        if len(chunks) <= 1 and "另外" in raw_text:
            chunks = [chunk.strip() for chunk in raw_text.split("另外") if chunk.strip()]
        return chunks

    def _card_from_segment(self, segment: str) -> ExtractorCard:
        classification = self._classify(segment)
        metadata_json = self._metadata(segment, classification.module_type)
        return ExtractorCard(
            module_type=classification.module_type,
            title=classification.title,
            summary=segment,
            content=segment,
            content_for_embedding=f"{classification.module_type.value}: {segment}",
            emotion_score=classification.emotion_score,
            importance_score=classification.importance_score,
            urgency_score=classification.urgency_score,
            status=CardStatus.open,
            privacy_level=PrivacyLevel.private,
            metadata_json=metadata_json,
        )

    def _classify(self, text: str) -> Classification:
        lowered = text.lower()
        if self._contains(lowered, GRATITUDE_WORDS):
            return Classification(CardModuleType.gratitude, "Gratitude", emotion_score=4, importance_score=6, urgency_score=3)
        if self._contains(lowered, FUTURE_SELF_WORDS):
            return Classification(CardModuleType.future_self, "Future-self reflection", emotion_score=7, importance_score=7, urgency_score=4)
        if self._contains(lowered, STUCK_WORDS):
            return Classification(CardModuleType.scaffolding, "Stuck problem", emotion_score=self._emotion_score(lowered), importance_score=7, urgency_score=6)
        if self._contains(lowered, DECISION_WORDS) and "不知道怎么开始" not in lowered:
            return Classification(CardModuleType.decision, "Decision", emotion_score=self._emotion_score(lowered), importance_score=8, urgency_score=self._urgency_score(lowered))
        if self._looks_avsi(lowered):
            return Classification(CardModuleType.avsi, "Knowledge topic", emotion_score=3, importance_score=6, urgency_score=3)
        if self._contains(lowered, TASK_WORDS):
            return Classification(CardModuleType.task, "Task", emotion_score=3, importance_score=5, urgency_score=self._urgency_score(lowered))
        if self._contains(lowered, EMOTION_WORDS):
            return Classification(CardModuleType.free_write, "Free write", emotion_score=self._emotion_score(lowered), importance_score=5, urgency_score=4)
        return Classification(CardModuleType.general, "General note", emotion_score=3, importance_score=4, urgency_score=2)

    def _metadata(self, text: str, module_type: CardModuleType) -> dict[str, Any]:
        topics = self._topics(text)
        people = self._people(text)
        return {
            "people": people,
            "topics": topics,
            "next_actions": [text] if module_type == CardModuleType.task else [],
            "predictions": [],
            "expected_outcome": None,
            "return_action": None,
            "check_reason": None,
        }

    def _topics(self, text: str) -> list[str]:
        topics: list[str] = []
        lowered = text.lower()
        known_topics = ["agent", "pgvector", "langgraph", "rag", "embedding", "postgres", "fastapi", "cognosos"]
        for topic in known_topics:
            if topic in lowered and topic not in topics:
                topics.append(topic)
        for match in TECH_TOPIC_RE.findall(text):
            topic = match.lower()
            if topic not in topics:
                topics.append(topic)
        if "认知引擎" in text:
            topics.append("认知引擎")
        return topics

    def _people(self, text: str) -> list[str]:
        return list(dict.fromkeys(match.group(1) for match in PERSON_RE.finditer(text)))

    def _looks_avsi(self, lowered: str) -> bool:
        return self._contains(lowered, AVSI_WORDS) and ("想" in lowered or "理解" in lowered or "搞懂" in lowered or "研究" in lowered)

    def _contains(self, text: str, words: tuple[str, ...]) -> bool:
        return any(word in text for word in words)

    def _emotion_score(self, text: str) -> int:
        if any(word in text for word in ("崩溃", "完全", "非常", "很焦虑", "overwhelmed")):
            return 8
        if any(word in text for word in EMOTION_WORDS):
            return 7
        return 4

    def _urgency_score(self, text: str) -> int:
        if any(word in text for word in ("今天", "明天", "马上", "立刻", "today", "tomorrow")):
            return 7
        return 4
