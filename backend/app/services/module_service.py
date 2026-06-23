from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.app.db.base import utc_now
from backend.app.models.db_models import CognitiveCard, ModuleRun, TimeCapsule, TriggerEvent
from backend.app.models.enums import (
    CardModuleType,
    CardStatus,
    ModuleRunStatus,
    PrivacyLevel,
    TimeCapsuleActionType,
    TimeCapsuleStatus,
    TriggerEventStatus,
    TriggerModuleType,
)
from backend.app.models.schemas import CognitiveCardCreate, ModuleRunRequest, TimeCapsuleCreate
from backend.app.services.card_service import create_card
from backend.app.services.embedding_service import embed_text
from backend.app.services.time_capsule_service import create_time_capsule


MODULE_QUESTIONS: dict[TriggerModuleType, list[str]] = {
    TriggerModuleType.decision: [
        "我今天做的决定是：",
        "我为什么这样选：",
        "我当时掌握的信息是：",
        "我当时的情绪是：",
        "我预期会发生什么：",
        "我什么时候 check：",
        "到时候主要检查什么：",
    ],
    TriggerModuleType.scaffolding: [
        "我要解决的问题是：",
        "为什么现在要解决：",
        "怎样算初步完成：",
        "当前状态是什么：",
        "它可以拆成哪 3 个子问题：",
        "我需要准备什么：",
        "10 分钟内的最小下一步是什么：",
        "24 小时内做什么：",
        "7 天内做什么：",
        "我什么时候 check：",
    ],
    TriggerModuleType.avsi: [
        "主题是什么：",
        "一句话介绍：",
        "它回应/解决什么问题：",
        "为什么重要：",
        "核心概念有哪些：",
        "基本结构是什么：",
        "运作机制是什么：",
        "主要争议是什么：",
        "常见误解是什么：",
        "我下一步要追问什么：",
    ],
    TriggerModuleType.future_self: [
        "明天的我会感谢今天的我做什么：",
        "明天的我会后悔今天的我没做什么：",
        "90 天后的我，如果状态变好了，是因为我从现在开始做了什么：",
        "90 天后的我，如果还卡住，最可能是因为我继续逃避什么：",
        "五年后的我会提醒我不要过度在意什么：",
        "现在最小的一步是什么：",
        "我什么时候 check：",
    ],
    TriggerModuleType.reciprocity: [
        "今天我感激谁：",
        "对方具体做了什么：",
        "这件事为什么对我重要：",
        "我可以怎么回应：",
        "我什么时候做：",
        "如果不能直接返还，我可以把善意传给谁：",
    ],
    TriggerModuleType.check_review: [
        "当时的预期是什么：",
        "实际发生了什么：",
        "判断哪里准确：",
        "判断哪里偏了：",
        "偏差主要来自信息不足、情绪影响、执行问题，还是运气因素：",
        "这个 card 应该关闭、继续、还是转成新问题：",
    ],
}


def get_module_questions(module_type: TriggerModuleType) -> list[str]:
    return MODULE_QUESTIONS[module_type]


def run_module(db: Session, module_type: TriggerModuleType, request: ModuleRunRequest) -> ModuleRun:
    answers = request.answers
    created_cards: list[CognitiveCard] = []
    created_capsules: list[TimeCapsule] = []
    input_card_ids = [str(card_id) for card_id in request.input_card_ids]

    trigger_event = db.get(TriggerEvent, request.trigger_event_id) if request.trigger_event_id else None
    if trigger_event is not None:
        trigger_event.status = TriggerEventStatus.accepted

    output = {
        "questions": get_module_questions(module_type),
        "summary": _summarize_answers(module_type, answers),
    }

    if module_type == TriggerModuleType.check_review:
        card = _create_module_card(db, module_type, request.input_card_ids, answers, output)
        created_cards.append(card)
        _apply_check_review_updates(db, request, answers)
    else:
        card = _create_module_card(db, module_type, request.input_card_ids, answers, output)
        created_cards.append(card)
        capsule = _create_module_capsule(db, module_type, card, answers)
        if capsule is not None:
            created_capsules.append(capsule)

    module_run = ModuleRun(
        module_type=module_type,
        trigger_event_id=request.trigger_event_id,
        input_card_ids=input_card_ids,
        answers=answers,
        output=output,
        created_card_ids=[str(card.id) for card in created_cards],
        created_time_capsule_ids=[str(capsule.id) for capsule in created_capsules],
        status=ModuleRunStatus.completed,
    )
    db.add(module_run)
    if trigger_event is not None:
        trigger_event.status = TriggerEventStatus.completed
        db.add(trigger_event)
    db.commit()
    db.refresh(module_run)
    return module_run


def _create_module_card(
    db: Session,
    module_type: TriggerModuleType,
    input_card_ids: list[uuid.UUID],
    answers: dict[str, Any],
    output: dict[str, Any],
) -> CognitiveCard:
    content = _answers_to_content(answers)
    summary = output["summary"] or content or module_type.value
    card_module_type = CardModuleType(module_type.value)
    metadata_json = {
        "people": _list_value(answers, "people", "今天我感激谁", "person"),
        "topics": _list_value(answers, "topics", "主题是什么", "topic"),
        "next_actions": _list_value(answers, "next_actions", "现在最小的一步是什么", "10 分钟内的最小下一步是什么"),
        "predictions": _list_value(answers, "predictions", "我预期会发生什么"),
        "expected_outcome": _answer(answers, "expected_outcome", "我预期会发生什么", "怎样算初步完成"),
        "return_action": _answer(answers, "return_action", "我可以怎么回应"),
        "check_reason": _answer(answers, "check_reason", "到时候主要检查什么", "我什么时候 check"),
        "input_card_ids": [str(card_id) for card_id in input_card_ids],
        "module_run": True,
    }
    vector, model_name, dimension = embed_text(f"{module_type.value}: {content or summary}")
    payload = CognitiveCardCreate(
        module_type=card_module_type,
        title=_answer(answers, "title", "主题是什么", "我要解决的问题是", "我今天做的决定是") or module_type.value,
        summary=summary,
        content=content or summary,
        content_for_embedding=f"{module_type.value}: {content or summary}",
        embedding=vector,
        embedding_model=model_name,
        embedding_dim=dimension,
        emotion_score=_score(answers, "emotion_score"),
        importance_score=_score(answers, "importance_score") or 7,
        urgency_score=_score(answers, "urgency_score") or 5,
        status=CardStatus.open,
        privacy_level=PrivacyLevel.private,
        metadata_json=metadata_json,
    )
    return create_card(db, payload)


def _create_module_capsule(
    db: Session,
    module_type: TriggerModuleType,
    card: CognitiveCard,
    answers: dict[str, Any],
) -> TimeCapsule | None:
    action_map = {
        TriggerModuleType.decision: TimeCapsuleActionType.check_decision,
        TriggerModuleType.scaffolding: TimeCapsuleActionType.review_scaffold,
        TriggerModuleType.future_self: TimeCapsuleActionType.review_future_self,
        TriggerModuleType.reciprocity: TimeCapsuleActionType.return_kindness,
    }
    if module_type == TriggerModuleType.avsi:
        if not _answer(answers, "trigger_at", "check_at", "我什么时候 check"):
            return None
        action_type = TimeCapsuleActionType.review_avsi_followup
    else:
        action_type = action_map.get(module_type)
    if action_type is None:
        return None

    trigger_at = _parse_trigger_at(answers, module_type)
    payload = TimeCapsuleCreate(
        card_id=card.id,
        action_type=action_type,
        title=_capsule_title(module_type, card),
        description=_answer(answers, "check_reason", "到时候主要检查什么", "我什么时候 check", "我什么时候做"),
        trigger_at=trigger_at,
    )
    return create_time_capsule(db, payload)


def _apply_check_review_updates(db: Session, request: ModuleRunRequest, answers: dict[str, Any]) -> None:
    status_answer = str(_answer(answers, "status", "这个 card 应该关闭、继续、还是转成新问题") or "").lower()
    for card_id in request.input_card_ids:
        card = db.get(CognitiveCard, card_id)
        if card is None:
            continue
        if any(word in status_answer for word in ("关闭", "close", "closed")):
            card.status = CardStatus.closed
        elif any(word in status_answer for word in ("继续", "open", "keep")):
            card.status = CardStatus.open
        elif any(word in status_answer for word in ("卡住", "stalled")):
            card.status = CardStatus.stalled
        db.add(card)

    if request.time_capsule_id is not None:
        capsule = db.get(TimeCapsule, request.time_capsule_id)
        if capsule is not None:
            capsule.status = TimeCapsuleStatus.resolved
            capsule.resolution_notes = _answer(answers, "resolution_notes") or "Resolved by check_review module."
            capsule.resolved_at = utc_now()
            db.add(capsule)


def _summarize_answers(module_type: TriggerModuleType, answers: dict[str, Any]) -> str:
    for key in ("summary", "title", "我要解决的问题是", "我今天做的决定是", "主题是什么", "现在最小的一步是什么"):
        value = answers.get(key)
        if value:
            return str(value)
    return f"{module_type.value} module run"


def _answers_to_content(answers: dict[str, Any]) -> str:
    if not answers:
        return ""
    return "\n".join(f"{key}: {value}" for key, value in answers.items())


def _parse_trigger_at(answers: dict[str, Any], module_type: TriggerModuleType) -> datetime:
    raw = _answer(answers, "trigger_at", "check_at", "我什么时候 check", "什么时候做", "我什么时候做")
    if raw:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    default_days = {
        TriggerModuleType.decision: 30,
        TriggerModuleType.scaffolding: 7,
        TriggerModuleType.future_self: 7,
        TriggerModuleType.reciprocity: 3,
        TriggerModuleType.avsi: 14,
    }.get(module_type, 7)
    return utc_now() + timedelta(days=default_days)


def _capsule_title(module_type: TriggerModuleType, card: CognitiveCard) -> str:
    labels = {
        TriggerModuleType.decision: "Decision check",
        TriggerModuleType.scaffolding: "Scaffold review",
        TriggerModuleType.future_self: "Future-self review",
        TriggerModuleType.reciprocity: "Return-kindness action",
        TriggerModuleType.avsi: "AVSI follow-up",
    }
    return f"{labels.get(module_type, 'Review')}: {card.title or card.summary[:40]}"


def _answer(answers: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in answers and answers[key] not in (None, ""):
            return answers[key]
    return None


def _list_value(answers: dict[str, Any], *keys: str) -> list[str]:
    value = _answer(answers, *keys)
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _score(answers: dict[str, Any], key: str) -> int | None:
    value = answers.get(key)
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return min(10, max(0, number))
