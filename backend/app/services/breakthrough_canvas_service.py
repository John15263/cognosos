from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.base import utc_now
from backend.app.models.db_models import CognitiveCard, RawEntry, TimeCapsule, TriggerEvent, WritingSession, WritingSessionStage
from backend.app.models.enums import (
    CardModuleType,
    CardStatus,
    ObsidianObjectType,
    PrivacyLevel,
    ProcessingStatus,
    RawEntrySource,
    TimeCapsuleActionType,
    WritingSessionStatus,
)
from backend.app.models.schemas import CognitiveCardCreate, EntryCreateResponse, FlowSessionCreate, FlowSessionResponse, TimeCapsuleCreate
from backend.app.services.card_service import create_card
from backend.app.services.embedding_service import embed_text
from backend.app.services.llm_service import get_llm_provider
from backend.app.services.obsidian_service import (
    append_breakthrough_canvas_to_daily_note,
    create_obsidian_link,
)
from backend.app.services.retrieval_service import retrieve_similar_cards
from backend.app.services.time_capsule_service import create_time_capsule
from backend.app.services.trigger_service import create_trigger_event, plan_trigger_decisions

STAGE_TO_CARD_TYPE: dict[str, CardModuleType] = {
    "mental_dump": CardModuleType.free_write,
    "future_reframe": CardModuleType.future_self,
    "decision_snapshot": CardModuleType.decision,
    "scaffold_action": CardModuleType.scaffolding,
    "morning_forecast": CardModuleType.prediction,
    "prediction_seal": CardModuleType.prediction,
}

DEFAULT_STAGE_SCORES: dict[str, tuple[int, int, int]] = {
    "mental_dump": (7, 6, 5),
    "future_reframe": (5, 7, 4),
    "decision_snapshot": (5, 8, 5),
    "scaffold_action": (4, 7, 6),
    "morning_forecast": (4, 7, 4),
    "prediction_seal": (4, 8, 5),
}

SKIPPED_STAGE_STATUSES = {"skipped", "failed"}
ASCII_WORD_RE = re.compile(r"[A-Za-z0-9_+#.-]+")
CJK_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


def create_breakthrough_canvas_session(db: Session, payload: FlowSessionCreate) -> FlowSessionResponse:
    now = utc_now()
    structured_payload = _structured_payload(payload)
    session = WritingSession(
        prompt_id=payload.prompt_id,
        prompt_title=payload.prompt_title,
        prompt_cues=payload.prompt_cues,
        mode=payload.mode,
        status=payload.status,
        duration_seconds=payload.duration_seconds,
        idle_timeout_seconds=payload.idle_timeout_seconds,
        final_word_count=payload.final_word_count,
        interruption_count=payload.interruption_count,
        structured_payload=structured_payload,
        pipeline_version=payload.pipeline_version or structured_payload.get("pipeline_version"),
        decision_stage_enabled=payload.decision_stage_enabled,
        content_hash=None,
        started_at=now,
        ended_at=now,
    )
    db.add(session)
    db.flush()

    stage_models = _save_stages(db, session, payload)
    raw_entry_id = None
    cards: list[CognitiveCard] = []
    time_capsules: list[TimeCapsule] = []
    trigger_events: list[TriggerEvent] = []
    if payload.status == WritingSessionStatus.completed and _has_stage_content(stage_models):
        raw_entry = RawEntry(
            content=_plain_stage_text(stage_models),
            source=RawEntrySource.text,
            processing_status=ProcessingStatus.received,
        )
        db.add(raw_entry)
        db.flush()
        session.raw_entry_id = raw_entry.id
        raw_entry_id = raw_entry.id

    db.add(session)
    db.commit()
    db.refresh(session)
    for stage in stage_models:
        db.refresh(stage)

    if raw_entry_id is not None:
        raw_entry = db.get(RawEntry, raw_entry_id)
        if raw_entry is None:
            raise RuntimeError(f"Raw entry {raw_entry_id} disappeared after local save.")
        try:
            cards = _create_stage_cards(db, session, raw_entry, stage_models)
            time_capsules = _create_stage_time_capsules(db, session, stage_models, cards)
            trigger_events = _create_stage_trigger_events(db, raw_entry, cards)
            raw_entry.processing_status = ProcessingStatus.processed
            raw_entry.error_message = _collect_nonfatal_processing_errors(cards)
            db.add(raw_entry)
            db.commit()
            for stage in stage_models:
                db.refresh(stage)
            for card in cards:
                db.refresh(card)
            for event in trigger_events:
                db.refresh(event)
            for capsule in time_capsules:
                db.refresh(capsule)
        except Exception as exc:
            db.rollback()
            raw_entry = db.get(RawEntry, raw_entry_id)
            if raw_entry is not None:
                raw_entry.processing_status = ProcessingStatus.failed
                raw_entry.error_message = f"Breakthrough processing failed after local capture: {exc}"
                db.add(raw_entry)
                db.commit()
            db.refresh(session)
            return FlowSessionResponse(
                session=session,
                entry=EntryCreateResponse(entry_id=raw_entry_id, cards=[], trigger_events=[], time_capsules=[]),
            )

    if raw_entry_id is not None:
        try:
            projection_heading = "Prediction Ledger" if structured_payload.get("writing_mode") == "prediction_ledger" else "Breakthrough Canvas"
            note_path, hash_value = append_breakthrough_canvas_to_daily_note(
                session_id=session.id,
                pipeline_version=session.pipeline_version,
                decision_stage_enabled=session.decision_stage_enabled,
                stages=stage_models,
                cards=cards,
                time_capsules=time_capsules,
                created_at=session.ended_at,
                heading=projection_heading,
                mode=str(structured_payload.get("writing_mode") or "breakthrough_canvas"),
            )
        except Exception as exc:
            db.rollback()
            raw_entry = db.get(RawEntry, raw_entry_id)
            if raw_entry is not None:
                raw_entry.error_message = _append_error(raw_entry.error_message, f"Obsidian projection failed: {exc}")
                db.add(raw_entry)
                db.commit()
            db.refresh(session)
            return FlowSessionResponse(
                session=session,
                entry=EntryCreateResponse(entry_id=raw_entry_id, cards=cards, trigger_events=trigger_events, time_capsules=time_capsules),
            )

        session.note_path = note_path
        session.content_hash = hash_value
        db.add(session)
        create_obsidian_link(db, ObsidianObjectType.writing_session, session.id, note_path, hash_value)
        create_obsidian_link(db, ObsidianObjectType.raw_entry, raw_entry_id, note_path, hash_value)
        for card in cards:
            create_obsidian_link(db, ObsidianObjectType.cognitive_card, card.id, note_path)
        for event in trigger_events:
            create_obsidian_link(db, ObsidianObjectType.trigger_event, event.id, note_path)
        for capsule in time_capsules:
            create_obsidian_link(db, ObsidianObjectType.time_capsule, capsule.id, note_path)
        db.commit()
        db.refresh(session)
        for card in cards:
            db.refresh(card)
        for event in trigger_events:
            db.refresh(event)
        for capsule in time_capsules:
            db.refresh(capsule)

    entry_response = (
        EntryCreateResponse(entry_id=raw_entry_id, cards=cards, trigger_events=trigger_events, time_capsules=time_capsules)
        if raw_entry_id is not None
        else None
    )
    return FlowSessionResponse(session=session, entry=entry_response)


def _structured_payload(payload: FlowSessionCreate) -> dict[str, Any]:
    if payload.structured_payload:
        data = dict(payload.structured_payload)
    else:
        data = {
            "writing_mode": "breakthrough_canvas",
            "pipeline_version": payload.pipeline_version or "v1.1_decision_gate",
            "decision_stage_enabled": payload.decision_stage_enabled,
            "stages": [stage.model_dump(mode="json") for stage in payload.stages],
        }
    if payload.compiled_markdown:
        data.setdefault("client_preview_markdown", payload.compiled_markdown)
    return data


def _save_stages(db: Session, session: WritingSession, payload: FlowSessionCreate) -> list[WritingSessionStage]:
    stages: list[WritingSessionStage] = []
    for stage in sorted(payload.stages, key=lambda item: item.stage_order):
        content = stage.content.strip()
        stage_model = WritingSessionStage(
            writing_session_id=session.id,
            stage_id=stage.stage_id,
            stage_order=stage.stage_order,
            module_type=stage.module_type,
            title=stage.title,
            prompt_label=stage.prompt_label,
            ghost_starter=stage.ghost_starter,
            content=content,
            word_count=stage.word_count or _count_words(content),
            status=stage.status,
            idle_timeout_seconds=stage.idle_timeout_seconds,
            interruption_count=stage.interruption_count,
            started_at=stage.started_at,
            completed_at=stage.completed_at,
            nudges_shown=stage.nudges_shown,
            metadata_json=stage.metadata_json,
        )
        db.add(stage_model)
        db.flush()
        stages.append(stage_model)
    return stages


def _create_stage_cards(
    db: Session,
    session: WritingSession,
    raw_entry: RawEntry,
    stages: list[WritingSessionStage],
) -> list[CognitiveCard]:
    cards: list[CognitiveCard] = []
    for stage in stages:
        if not _is_actionable_stage(stage):
            continue
        card_type = STAGE_TO_CARD_TYPE.get(stage.stage_id, stage.module_type)
        content_for_embedding = f"{card_type.value}: {stage.content}"
        embedding_error: str | None = None
        try:
            vector, model_name, dimension = embed_text(content_for_embedding)
        except Exception as exc:
            vector = None
            model_name = None
            dimension = get_settings().embedding_dim
            embedding_error = f"{type(exc).__name__}: {exc}"
        emotion_score, importance_score, urgency_score = DEFAULT_STAGE_SCORES.get(stage.stage_id, (4, 5, 3))
        writing_mode = str((session.structured_payload or {}).get("writing_mode") or "breakthrough_canvas")
        metadata_json = {
            "pipeline": writing_mode,
            "pipeline_version": session.pipeline_version,
            "stage_id": stage.stage_id,
            "stage_order": stage.stage_order,
            "stage_status": stage.status,
            "topics": [],
            "people": [],
            "next_actions": [stage.content] if card_type == CardModuleType.scaffolding else [],
            "predictions": [stage.content] if card_type in {CardModuleType.decision, CardModuleType.prediction} else [],
            "expected_outcome": None,
            "check_reason": None,
            **(stage.metadata_json or {}),
        }
        if embedding_error is not None:
            metadata_json["embedding_error"] = embedding_error
        card = create_card(
            db,
            CognitiveCardCreate(
                entry_id=raw_entry.id,
                source_session_id=session.id,
                source_stage_id=stage.id,
                module_type=card_type,
                title=stage.title or stage.prompt_label or stage.stage_id,
                summary=_summary(stage.content),
                content=stage.content,
                content_for_embedding=content_for_embedding,
                embedding=vector,
                embedding_model=model_name,
                embedding_dim=dimension,
                emotion_score=emotion_score,
                importance_score=importance_score,
                urgency_score=urgency_score,
                status=CardStatus.open,
                privacy_level=PrivacyLevel.private,
                metadata_json=metadata_json,
            ),
        )
        stage.created_card_id = card.id
        db.add(stage)
        cards.append(card)
    _link_prediction_seal_cards(cards)
    db.flush()
    return cards


def _link_prediction_seal_cards(cards: list[CognitiveCard]) -> None:
    anchor_ids = {
        card.module_type.value: str(card.id)
        for card in cards
        if card.module_type in {CardModuleType.decision, CardModuleType.scaffolding}
    }
    if not anchor_ids:
        return
    for card in cards:
        if (card.metadata_json or {}).get("stage_id") != "prediction_seal":
            continue
        card.metadata_json = {
            **(card.metadata_json or {}),
            "linked_card_ids": anchor_ids,
        }


def _create_stage_time_capsules(
    db: Session,
    session: WritingSession,
    stages: list[WritingSessionStage],
    cards: list[CognitiveCard],
) -> list[TimeCapsule]:
    card_by_stage_id = {str(card.source_stage_id): card for card in cards if card.source_stage_id is not None}
    prediction_stage = next((stage for stage in stages if stage.stage_id == "prediction_seal" and _is_actionable_stage(stage)), None)
    has_anchor_capsule = any(
        stage.stage_id in {"decision_snapshot", "scaffold_action"} and _is_actionable_stage(stage)
        for stage in stages
    )
    capsules: list[TimeCapsule] = []
    for stage in stages:
        if not _is_actionable_stage(stage):
            continue
        if stage.stage_id == "prediction_seal" and has_anchor_capsule:
            continue
        card = card_by_stage_id.get(str(stage.id))
        if card is None:
            continue
        payload = _capsule_payload(
            session,
            stage,
            card,
            prediction_stage=prediction_stage if stage.stage_id in {"decision_snapshot", "scaffold_action"} else None,
        )
        if payload is not None:
            capsules.append(create_time_capsule(db, payload))
    db.flush()
    return capsules


def _prediction_note(stage: WritingSessionStage | None) -> str:
    if stage is None or not stage.content.strip():
        return ""
    return f"\n\nPrediction Seal:\n{_trim(stage.content, 900)}"


def _capsule_payload(
    session: WritingSession,
    stage: WritingSessionStage,
    card: CognitiveCard,
    prediction_stage: WritingSessionStage | None = None,
) -> TimeCapsuleCreate | None:
    check_at = _metadata_check_at(stage)
    prediction_note = _prediction_note(prediction_stage)
    if stage.stage_id == "decision_snapshot":
        return TimeCapsuleCreate(
            card_id=card.id,
            source_session_id=session.id,
            source_stage_id=stage.id,
            action_type=TimeCapsuleActionType.check_decision,
            title="Review decision prediction",
            description=f"当时写下的判断/预期：\n{_trim(stage.content, 900)}{prediction_note}",
            trigger_at=check_at or utc_now() + timedelta(days=7),
        )
    if stage.stage_id == "scaffold_action":
        return TimeCapsuleCreate(
            card_id=card.id,
            source_session_id=session.id,
            source_stage_id=stage.id,
            action_type=TimeCapsuleActionType.review_scaffold,
            title="Review scaffold next action",
            description=f"当时写下的最小行动/成功标准：\n{_trim(stage.content, 900)}{prediction_note}",
            trigger_at=check_at or utc_now() + timedelta(days=3),
        )
    if stage.stage_id in {"morning_forecast", "prediction_seal"}:
        return TimeCapsuleCreate(
            card_id=card.id,
            source_session_id=session.id,
            source_stage_id=stage.id,
            action_type=TimeCapsuleActionType.review_prediction,
            title="Review prediction seal" if stage.stage_id == "prediction_seal" else "Review morning forecast",
            description=f"写下的预测：\n{_trim(stage.content, 900)}",
            trigger_at=check_at or _default_evening_check_at(),
        )
    return None


def _create_stage_trigger_events(db: Session, raw_entry: RawEntry, cards: list[CognitiveCard]) -> list[TriggerEvent]:
    trigger_events: list[TriggerEvent] = []
    try:
        llm_provider = get_llm_provider()
    except Exception as exc:
        _mark_trigger_error(db, cards, exc)
        return []
    for card in cards:
        try:
            historical_context = retrieve_similar_cards(
                db,
                query_embedding=card.embedding or [],
                statuses=[CardStatus.open, CardStatus.stalled, CardStatus.closed],
                days_back=90,
                limit=12,
                min_similarity=0.35,
                exclude_entry_id=raw_entry.id,
            )
            candidates = plan_trigger_decisions(db, card, historical_context)
            decisions = llm_provider.judge_triggers(candidates)
            for decision in decisions:
                event = create_trigger_event(db, card, decision)
                if event is not None:
                    trigger_events.append(event)
        except Exception as exc:
            card.metadata_json = {
                **(card.metadata_json or {}),
                "trigger_judge_error": f"{type(exc).__name__}: {exc}",
            }
            db.add(card)
    db.flush()
    return trigger_events


def _mark_trigger_error(db: Session, cards: list[CognitiveCard], exc: Exception) -> None:
    error = f"{type(exc).__name__}: {exc}"
    for card in cards:
        card.metadata_json = {
            **(card.metadata_json or {}),
            "trigger_judge_error": error,
        }
        db.add(card)
    db.flush()


def _collect_nonfatal_processing_errors(cards: list[CognitiveCard]) -> str | None:
    errors: list[str] = []
    for card in cards:
        metadata = card.metadata_json or {}
        if metadata.get("embedding_error"):
            errors.append(f"{card.module_type.value} embedding: {metadata['embedding_error']}")
        if metadata.get("trigger_judge_error"):
            errors.append(f"{card.module_type.value} trigger judge: {metadata['trigger_judge_error']}")
    if not errors:
        return None
    return "Partial breakthrough processing errors: " + " | ".join(errors)


def _append_error(existing: str | None, message: str) -> str:
    return f"{existing} | {message}" if existing else message


def _has_stage_content(stages: list[WritingSessionStage]) -> bool:
    return any(_is_actionable_stage(stage) for stage in stages)


def _is_actionable_stage(stage: WritingSessionStage) -> bool:
    return stage.status not in SKIPPED_STAGE_STATUSES and bool(stage.content.strip())


def _plain_stage_text(stages: list[WritingSessionStage]) -> str:
    return "\n\n".join(f"{stage.prompt_label or stage.stage_id}\n{stage.content}" for stage in stages if stage.content.strip())


def _count_words(text: str) -> int:
    return len(ASCII_WORD_RE.findall(text)) + len(CJK_CHAR_RE.findall(text))


def _summary(text: str) -> str:
    normalized = " ".join(text.split())
    return _trim(normalized, 180) or "Breakthrough Canvas stage"


def _trim(text: str, limit: int) -> str:
    normalized = text.strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1]}..."


def _metadata_check_at(stage: WritingSessionStage) -> datetime | None:
    raw = (stage.metadata_json or {}).get("check_at")
    if not isinstance(raw, str) or not raw.strip():
        return None
    value = raw.strip()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _default_evening_check_at() -> datetime:
    now = utc_now()
    target = now.replace(hour=21, minute=0, second=0, microsecond=0)
    return target if target > now else target + timedelta(days=1)
