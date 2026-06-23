from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from backend.app.models.enums import CardModuleType, CardStatus, PrivacyLevel, TriggerModuleType
from backend.app.models.schemas import ExtractorOutput, TriggerDecision
from backend.app.providers.llm_base import LLMProvider


class GeminiJudgeOutput(BaseModel):
    decisions: list[TriggerDecision] = Field(default_factory=list)


class GeminiLLMProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-3.5-flash",
        client: Any | None = None,
    ) -> None:
        if not api_key and client is None:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini LLM calls.")

        self.model_name = model_name
        try:
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("google-genai is not installed. Install with `pip install -e '.[gemini]'`.") from exc

        self._types = types
        if client is not None:
            self._client = client
            return

        try:
            from google import genai
        except ImportError as exc:
            raise RuntimeError("google-genai is not installed. Install with `pip install -e '.[gemini]'`.") from exc

        self._client = genai.Client(api_key=api_key)

    def extract_cards(self, raw_text: str) -> ExtractorOutput:
        prompt = self._extractor_prompt(raw_text)
        return self._generate_validated(prompt, ExtractorOutput)

    def judge_triggers(self, candidates: list[TriggerDecision]) -> list[TriggerDecision]:
        if not candidates:
            return []
        prompt = self._judge_prompt(candidates)
        output = self._generate_validated(prompt, GeminiJudgeOutput)
        return output.decisions

    def _generate_validated(self, prompt: str, schema_model: type[BaseModel]) -> Any:
        last_error: Exception | None = None
        for attempt in range(2):
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt if attempt == 0 else f"{prompt}\n\nPrevious output was invalid. Return valid JSON only.",
                config=self._generate_config(schema_model),
            )
            text = getattr(response, "text", None)
            if text is None and isinstance(response, dict):
                text = response.get("text")
            if not text:
                last_error = ValueError("Gemini returned an empty response.")
                continue

            try:
                return schema_model.model_validate_json(text)
            except Exception as exc:
                last_error = exc

        raise ValueError(f"Gemini returned invalid JSON: {last_error}") from last_error

    def _generate_config(self, schema_model: type[BaseModel]) -> Any:
        return self._types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=self._response_schema(schema_model),
            safety_settings=self._safety_settings(),
        )

    def _response_schema(self, schema_model: type[BaseModel]) -> dict[str, Any]:
        if schema_model is ExtractorOutput:
            return _extractor_response_schema()
        if schema_model is GeminiJudgeOutput:
            return _judge_response_schema()
        return schema_model.model_json_schema()

    def _safety_settings(self) -> list[Any]:
        categories = (
            self._types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            self._types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            self._types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            self._types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            self._types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
        )
        return [
            self._types.SafetySetting(
                category=category,
                threshold=self._types.HarmBlockThreshold.BLOCK_NONE,
            )
            for category in categories
        ]

    def _extractor_prompt(self, raw_text: str) -> str:
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
8. Output JSON matching the provided schema only.
9. metadata_json must include people, topics, next_actions, predictions, expected_outcome, return_action, check_reason.

Raw journal entry:
{raw_text}
""".strip()

    def _judge_prompt(self, candidates: list[TriggerDecision]) -> str:
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
7. Return JSON matching the provided schema only.

Deterministic candidates:
{json.dumps(payload, ensure_ascii=False)}
""".strip()


def _extractor_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "cards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "module_type": {"type": "string", "enum": [item.value for item in CardModuleType]},
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                        "content": {"type": "string"},
                        "content_for_embedding": {"type": "string"},
                        "emotion_score": {"type": "integer", "minimum": 0, "maximum": 10},
                        "importance_score": {"type": "integer", "minimum": 0, "maximum": 10},
                        "urgency_score": {"type": "integer", "minimum": 0, "maximum": 10},
                        "status": {"type": "string", "enum": [item.value for item in CardStatus]},
                        "privacy_level": {"type": "string", "enum": [item.value for item in PrivacyLevel]},
                        "metadata_json": {
                            "type": "object",
                            "properties": {
                                "people": {"type": "array", "items": {"type": "string"}},
                                "topics": {"type": "array", "items": {"type": "string"}},
                                "next_actions": {"type": "array", "items": {"type": "string"}},
                                "predictions": {"type": "array", "items": {"type": "string"}},
                                "expected_outcome": {"type": "string", "nullable": True},
                                "return_action": {"type": "string", "nullable": True},
                                "check_reason": {"type": "string", "nullable": True},
                            },
                        },
                    },
                    "required": ["module_type", "summary", "content", "content_for_embedding"],
                },
            }
        },
        "required": ["cards"],
    }


def _judge_response_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "triggered": {"type": "boolean"},
                        "triggered_module": {"type": "string", "enum": [item.value for item in TriggerModuleType]},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                        "reason": {"type": "string"},
                        "evidence_card_ids": {"type": "array", "items": {"type": "string"}},
                        "intervention_level": {"type": "integer", "minimum": 0, "maximum": 3},
                        "next_question": {"type": "string"},
                    },
                    "required": ["triggered"],
                },
            }
        },
        "required": ["decisions"],
    }
