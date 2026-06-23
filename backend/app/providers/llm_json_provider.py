from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from backend.app.models.enums import (
    CardModuleType,
    CardStatus,
    PrivacyLevel,
    TriggerModuleType,
)
from backend.app.models.schemas import ExtractorOutput, TriggerDecision
from backend.app.providers.llm_base import LLMProvider

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class JudgeOutput(BaseModel):
    decisions: list[TriggerDecision] = Field(default_factory=list)


def _enum_values(enum_cls: type) -> str:
    return ", ".join(item.value for item in enum_cls)


def _strip_code_fence(text: str) -> str:
    """Some chat models wrap JSON in ```json fences; remove them before parsing."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = _CODE_FENCE_RE.sub("", stripped).strip()
    return stripped


def extractor_prompt(raw_text: str) -> str:
    return f"""
You are the Capture Extractor for CognosOS.

Convert the user's raw journal entry into separate cognitive cards.

Rules:
1. Do not give advice.
2. Do not comfort, diagnose, moralize, or chat.
3. Split mixed content into multiple cards.
4. Each card must have exactly one main function.
5. Preserve concrete details.
6. Use the same language as the user.
7. Infer scores conservatively.
8. Output JSON only — no markdown, no prose, no code fences.
9. metadata_json must include people, topics, next_actions, predictions, expected_outcome, return_action, check_reason.

Return a JSON object of this exact shape:
{{
  "cards": [
    {{
      "module_type": "<one of: {_enum_values(CardModuleType)}>",
      "title": "<short title or null>",
      "summary": "<required>",
      "content": "<required>",
      "content_for_embedding": "<required>",
      "emotion_score": <integer 0-10 or null>,
      "importance_score": <integer 0-10 or null>,
      "urgency_score": <integer 0-10 or null>,
      "status": "<one of: {_enum_values(CardStatus)}>",
      "privacy_level": "<one of: {_enum_values(PrivacyLevel)}>",
      "metadata_json": {{
        "people": [],
        "topics": [],
        "next_actions": [],
        "predictions": [],
        "expected_outcome": null,
        "return_action": null,
        "check_reason": null
      }}
    }}
  ]
}}

Raw journal entry:
{raw_text}
""".strip()


def judge_prompt(candidates: list[TriggerDecision]) -> str:
    payload = [candidate.model_dump(mode="json") for candidate in candidates]
    return f"""
You are the AI Judge Router for CognosOS.

Decide whether to keep each deterministic trigger candidate or suppress it.

Rules:
1. Do not over-trigger.
2. Memory is for routing, not chatting.
3. If evidence is weak, return triggered=false for that item or omit it.
4. If triggered=true, keep a short reason based on specific evidence.
5. Do not diagnose mental health conditions.
6. Prefer the lowest sufficient intervention level.
7. Output JSON only — no markdown, no prose, no code fences.

Return a JSON object of this exact shape:
{{
  "decisions": [
    {{
      "triggered": <boolean, required>,
      "triggered_module": "<one of: {_enum_values(TriggerModuleType)} or null>",
      "confidence": <number 0-1 or null>,
      "reason": "<string or null>",
      "evidence_card_ids": [],
      "intervention_level": <integer 0-3 or null>,
      "next_question": "<string or null>"
    }}
  ]
}}

Deterministic candidates:
{json.dumps(payload, ensure_ascii=False)}
""".strip()


class JSONChatLLMProvider(LLMProvider):
    """Base for chat-completion LLMs that return JSON we validate with Pydantic.

    Subclasses implement ``_complete(prompt)`` to call their SDK and return the raw
    text response. The extractor/judge prompts and the validate-and-retry loop are
    shared so each concrete provider stays a thin client wrapper.
    """

    def extract_cards(self, raw_text: str) -> ExtractorOutput:
        return self._generate_validated(extractor_prompt(raw_text), ExtractorOutput)

    def judge_triggers(self, candidates: list[TriggerDecision]) -> list[TriggerDecision]:
        if not candidates:
            return []
        output = self._generate_validated(judge_prompt(candidates), JudgeOutput)
        return output.decisions

    def _generate_validated(self, prompt: str, schema_model: type[BaseModel]):
        last_error: Exception | None = None
        for attempt in range(2):
            text = self._complete(
                prompt
                if attempt == 0
                else f"{prompt}\n\nPrevious output was invalid. Return valid JSON only."
            )
            text = _strip_code_fence(text or "")
            if not text:
                last_error = ValueError("LLM returned an empty response.")
                continue
            try:
                return schema_model.model_validate_json(text)
            except Exception as exc:  # noqa: BLE001 - retry on any validation/parse error
                last_error = exc

        raise ValueError(f"LLM returned invalid JSON: {last_error}") from last_error

    def _complete(self, prompt: str) -> str:
        raise NotImplementedError
