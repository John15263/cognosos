from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.base import utc_now
from backend.app.models.db_models import CognitiveCard, TimeCapsule, TriggerEvent
from backend.app.models.enums import (
    CardModuleType,
    CardStatus,
    TimeCapsuleActionType,
    TimeCapsuleStatus,
    TriggerEventStatus,
    TriggerModuleType,
)
from backend.app.models.schemas import SearchResult, TriggerDecision

DECISION_WORDS = ("决定", "要不要", "是否", "选择", "放弃", "开始", "停止", "commit", "choose", "decide")
STUCK_WORDS = ("卡住", "不知道怎么开始", "拖延", "太复杂", "无从下手", "stuck", "procrastinating", "too complex", "don't know where to start")
TECH_TOPIC_HINTS = ("agent", "pgvector", "langgraph", "rag", "embedding", "postgres", "fastapi", "认知引擎")


def plan_trigger_decisions(
    db: Session,
    current_card: CognitiveCard,
    historical_context: list[SearchResult],
) -> list[TriggerDecision]:
    candidates: list[TriggerDecision] = []
    candidates.extend(_decision_rule(current_card))
    candidates.extend(_future_self_rule(current_card, historical_context))
    candidates.extend(_scaffolding_rule(db, current_card, historical_context))
    candidates.extend(_avsi_rule(db, current_card))
    candidates.extend(_reciprocity_rule(db, current_card))
    return _dedupe_decisions(candidates)


def create_trigger_event(
    db: Session,
    current_card: CognitiveCard | None,
    decision: TriggerDecision,
) -> TriggerEvent | None:
    if not decision.triggered or decision.triggered_module is None or decision.reason is None:
        return None

    event = TriggerEvent(
        triggered_module=decision.triggered_module,
        current_card_id=current_card.id if current_card else None,
        reason=decision.reason,
        evidence_card_ids=decision.evidence_card_ids,
        evidence={"next_question": decision.next_question} if decision.next_question else {},
        intervention_level=decision.intervention_level or 1,
        confidence=decision.confidence,
        status=TriggerEventStatus.suggested,
    )
    db.add(event)
    db.flush()
    return event


def list_trigger_events(db: Session, status: TriggerEventStatus | None = None) -> list[TriggerEvent]:
    stmt = select(TriggerEvent)
    if status is not None:
        stmt = stmt.where(TriggerEvent.status == status)
    return list(db.scalars(stmt.order_by(TriggerEvent.created_at.desc())))


def update_trigger_status(db: Session, trigger_id: uuid.UUID, status: TriggerEventStatus) -> TriggerEvent | None:
    event = db.get(TriggerEvent, trigger_id)
    if event is None:
        return None
    event.status = status
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_due_capsule_triggers(db: Session) -> tuple[list[TimeCapsule], list[TriggerEvent]]:
    due_capsules = list(
        db.scalars(
            select(TimeCapsule)
            .where(
                TimeCapsule.status == TimeCapsuleStatus.pending,
                TimeCapsule.trigger_at <= utc_now(),
            )
            .order_by(TimeCapsule.trigger_at.asc())
        )
    )
    events: list[TriggerEvent] = []
    for capsule in due_capsules:
        capsule.status = TimeCapsuleStatus.triggered
        decision = TriggerDecision(
            triggered=True,
            triggered_module=TriggerModuleType.check_review,
            confidence=1.0,
            reason=f"Time capsule is due: {capsule.title}",
            evidence_card_ids=[str(capsule.card_id)] if capsule.card_id else [],
            intervention_level=2,
            next_question="当时的预期和实际发生了什么？",
        )
        event = create_trigger_event(db, None, decision)
        if event is not None:
            events.append(event)
    db.commit()
    for capsule in due_capsules:
        db.refresh(capsule)
    for event in events:
        db.refresh(event)
    return due_capsules, events


def _decision_rule(card: CognitiveCard) -> list[TriggerDecision]:
    if (card.metadata_json or {}).get("pipeline") == "breakthrough_canvas" and card.module_type != CardModuleType.decision:
        return []
    text = card.content.lower()
    has_decision_language = any(word in text for word in DECISION_WORDS) and "不知道怎么开始" not in text
    if (card.module_type == CardModuleType.decision and (card.importance_score or 0) >= 7) or has_decision_language:
        return [
            TriggerDecision(
                triggered=True,
                triggered_module=TriggerModuleType.decision,
                confidence=0.85,
                reason="Important decision detected. The system should capture rationale, expected outcome, and check time.",
                evidence_card_ids=[],
                intervention_level=2,
                next_question="这个决定的预期结果是什么，什么时候回来检查？",
            )
        ]
    return []


def _future_self_rule(card: CognitiveCard, historical_context: list[SearchResult]) -> list[TriggerDecision]:
    settings = get_settings()
    if card.module_type not in {CardModuleType.free_write, CardModuleType.future_self}:
        return []
    if (card.emotion_score or 0) < 8:
        return []
    cutoff = utc_now() - timedelta(days=settings.trigger_short_window_days)
    evidence = [
        result
        for result in historical_context
        if result.status in {CardStatus.open, CardStatus.stalled}
        and result.similarity >= settings.trigger_high_similarity
        and _on_or_after(result.created_at, cutoff)
    ]
    if len(evidence) < 2:
        return []
    return [
        TriggerDecision(
            triggered=True,
            triggered_module=TriggerModuleType.future_self,
            confidence=0.82,
            reason="Repeated high-intensity emotional loop detected.",
            evidence_card_ids=[str(result.card_id) for result in evidence[:5]],
            intervention_level=2,
            next_question="明天的你会感谢今天的你做哪一个最小动作？",
        )
    ]


def _scaffolding_rule(db: Session, card: CognitiveCard, historical_context: list[SearchResult]) -> list[TriggerDecision]:
    text = card.content.lower()
    if not any(word in text for word in STUCK_WORDS):
        return []
    cutoff = utc_now() - timedelta(days=get_settings().trigger_medium_window_days)
    evidence = [
        result
        for result in historical_context
        if result.status in {CardStatus.open, CardStatus.stalled} and _on_or_after(result.created_at, cutoff)
    ]
    evidence_ids = [str(result.card_id) for result in evidence]
    for evidence_card in _recent_stuck_cards(db, set((card.metadata_json or {}).get("topics", [])), exclude_entry_id=card.entry_id):
        if str(evidence_card.id) not in evidence_ids:
            evidence_ids.append(str(evidence_card.id))
    if len(evidence) < 2:
        if len(evidence_ids) < 2:
            return []
    topics = set((card.metadata_json or {}).get("topics", []))
    if _has_active_scaffold(db, topics):
        return []
    return [
        TriggerDecision(
            triggered=True,
            triggered_module=TriggerModuleType.scaffolding,
            confidence=0.88,
            reason="Repeated unresolved problem without an active next-action scaffold.",
            evidence_card_ids=evidence_ids[:5],
            intervention_level=3,
            next_question="你要解决的问题用一句话怎么说？",
        )
    ]


def _avsi_rule(db: Session, card: CognitiveCard) -> list[TriggerDecision]:
    topics = set((card.metadata_json or {}).get("topics", []))
    if not topics:
        return []
    text = card.content.lower()
    is_topic_card = card.module_type == CardModuleType.avsi or bool(topics.intersection(TECH_TOPIC_HINTS)) or any(hint in text for hint in TECH_TOPIC_HINTS)
    if not is_topic_card:
        return []

    for topic in topics:
        if _has_existing_avsi(db, topic, exclude_card_id=card.id):
            continue
        count = _topic_card_count(db, topic, days_back=30, exclude_entry_id=card.entry_id) + 1
        if count >= 3:
            return [
                TriggerDecision(
                    triggered=True,
                    triggered_module=TriggerModuleType.avsi,
                    confidence=0.74,
                    reason="Repeated knowledge topic without a structural map.",
                    evidence_card_ids=_topic_evidence_ids(db, topic, days_back=30, exclude_entry_id=card.entry_id),
                    intervention_level=1,
                    next_question=f"{topic} 要先画一页结构图吗？",
                )
            ]
    return []


def _reciprocity_rule(db: Session, card: CognitiveCard) -> list[TriggerDecision]:
    if card.module_type != CardModuleType.gratitude:
        return []
    people = (card.metadata_json or {}).get("people", [])
    for person in people:
        count = _gratitude_person_count(db, person, days_back=30, exclude_entry_id=card.entry_id) + 1
        if count >= 2 and not _has_pending_return_kindness(db):
            return [
                TriggerDecision(
                    triggered=True,
                    triggered_module=TriggerModuleType.reciprocity,
                    confidence=0.78,
                    reason="Repeated gratitude toward the same person without a return-kindness action.",
                    evidence_card_ids=_gratitude_evidence_ids(db, person, days_back=30, exclude_entry_id=card.entry_id),
                    intervention_level=1,
                    next_question=f"你想怎么回应 {person} 的帮助？",
                )
            ]
    return []


def _has_active_scaffold(db: Session, topics: set[str]) -> bool:
    if not topics:
        return False
    cards = db.scalars(
        select(CognitiveCard).where(
            CognitiveCard.module_type == CardModuleType.scaffolding,
            CognitiveCard.status.in_([CardStatus.open, CardStatus.waiting, CardStatus.stalled]),
        )
    )
    return any(
        (card.metadata_json or {}).get("module_run") is True
        and topics.intersection(set((card.metadata_json or {}).get("topics", [])))
        for card in cards
    )


def _has_existing_avsi(db: Session, topic: str, exclude_card_id: uuid.UUID) -> bool:
    cards = db.scalars(
        select(CognitiveCard).where(
            CognitiveCard.id != exclude_card_id,
            CognitiveCard.module_type == CardModuleType.avsi,
            CognitiveCard.status.in_([CardStatus.open, CardStatus.closed]),
        )
    )
    return any(
        (card.metadata_json or {}).get("module_run") is True and topic in (card.metadata_json or {}).get("topics", [])
        for card in cards
    )


def _topic_card_count(db: Session, topic: str, days_back: int, exclude_entry_id: uuid.UUID | None) -> int:
    cards = _recent_cards(db, days_back, exclude_entry_id)
    return sum(1 for card in cards if topic in (card.metadata_json or {}).get("topics", []))


def _topic_evidence_ids(db: Session, topic: str, days_back: int, exclude_entry_id: uuid.UUID | None) -> list[str]:
    return [str(card.id) for card in _recent_cards(db, days_back, exclude_entry_id) if topic in (card.metadata_json or {}).get("topics", [])][:5]


def _gratitude_person_count(db: Session, person: str, days_back: int, exclude_entry_id: uuid.UUID | None) -> int:
    cards = _recent_cards(db, days_back, exclude_entry_id)
    return sum(
        1
        for card in cards
        if card.module_type == CardModuleType.gratitude and person in (card.metadata_json or {}).get("people", [])
    )


def _gratitude_evidence_ids(db: Session, person: str, days_back: int, exclude_entry_id: uuid.UUID | None) -> list[str]:
    return [
        str(card.id)
        for card in _recent_cards(db, days_back, exclude_entry_id)
        if card.module_type == CardModuleType.gratitude and person in (card.metadata_json or {}).get("people", [])
    ][:5]


def _recent_cards(db: Session, days_back: int, exclude_entry_id: uuid.UUID | None) -> list[CognitiveCard]:
    stmt = select(CognitiveCard).where(CognitiveCard.created_at >= utc_now() - timedelta(days=days_back))
    if exclude_entry_id is not None:
        stmt = stmt.where(CognitiveCard.entry_id != exclude_entry_id)
    return list(db.scalars(stmt))


def _recent_stuck_cards(db: Session, topics: set[str], exclude_entry_id: uuid.UUID | None) -> list[CognitiveCard]:
    cards = _recent_cards(db, get_settings().trigger_medium_window_days, exclude_entry_id)
    output: list[CognitiveCard] = []
    for card in cards:
        if card.status not in {CardStatus.open, CardStatus.stalled}:
            continue
        content = card.content.lower()
        card_topics = set((card.metadata_json or {}).get("topics", []))
        if any(word in content for word in STUCK_WORDS) and (not topics or topics.intersection(card_topics)):
            output.append(card)
    return output


def _has_pending_return_kindness(db: Session) -> bool:
    return (
        db.scalar(
            select(TimeCapsule.id).where(
                TimeCapsule.action_type == TimeCapsuleActionType.return_kindness,
                TimeCapsule.status == TimeCapsuleStatus.pending,
            )
        )
        is not None
    )


def _dedupe_decisions(decisions: list[TriggerDecision]) -> list[TriggerDecision]:
    priority = {
        TriggerModuleType.check_review: 0,
        TriggerModuleType.scaffolding: 1,
        TriggerModuleType.future_self: 2,
        TriggerModuleType.decision: 3,
        TriggerModuleType.avsi: 4,
        TriggerModuleType.reciprocity: 5,
    }
    seen: set[TriggerModuleType] = set()
    output: list[TriggerDecision] = []
    for decision in sorted(decisions, key=lambda item: priority.get(item.triggered_module, 99)):
        if decision.triggered_module is None or decision.triggered_module in seen:
            continue
        seen.add(decision.triggered_module)
        output.append(decision)
    return output


def _on_or_after(value: datetime, cutoff: datetime) -> bool:
    if value.tzinfo is None and cutoff.tzinfo is not None:
        cutoff = cutoff.replace(tzinfo=None)
    return value >= cutoff
