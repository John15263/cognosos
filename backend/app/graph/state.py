from __future__ import annotations

from typing import Any, TypedDict


class IngestionState(TypedDict, total=False):
    entry_id: str
    raw_input: str
    source: str
    extracted_cards: list[dict[str, Any]]
    embedded_cards: list[dict[str, Any]]
    historical_context: dict[str, list[dict[str, Any]]]
    trigger_candidates: list[dict[str, Any]]
    judge_decisions: list[dict[str, Any]]
    planned_time_capsules: list[dict[str, Any]]
    planned_trigger_events: list[dict[str, Any]]
    response: dict[str, Any]
    errors: list[str]


class DueCapsuleState(TypedDict, total=False):
    now: str
    due_capsules: list[dict[str, Any]]
    planned_trigger_events: list[dict[str, Any]]
    response: dict[str, Any]


class ModuleRunState(TypedDict, total=False):
    module_type: str
    trigger_event_id: str | None
    input_card_ids: list[str]
    answers: dict[str, Any]
    output_card: dict[str, Any] | None
    planned_time_capsules: list[dict[str, Any]]
    module_run: dict[str, Any]
    response: dict[str, Any]

