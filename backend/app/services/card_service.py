from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import utc_now
from backend.app.models.db_models import CognitiveCard
from backend.app.models.enums import CardModuleType, CardStatus
from backend.app.models.schemas import CognitiveCardCreate, CognitiveCardUpdate


def create_card(db: Session, payload: CognitiveCardCreate) -> CognitiveCard:
    card = CognitiveCard(**payload.model_dump())
    db.add(card)
    db.flush()
    return card


def get_card(db: Session, card_id: uuid.UUID) -> CognitiveCard | None:
    return db.get(CognitiveCard, card_id)


def list_cards(
    db: Session,
    module_type: CardModuleType | None = None,
    status: CardStatus | None = None,
    topic: str | None = None,
    person: str | None = None,
    days_back: int | None = None,
) -> list[CognitiveCard]:
    stmt = select(CognitiveCard)

    if module_type is not None:
        stmt = stmt.where(CognitiveCard.module_type == module_type)
    if status is not None:
        stmt = stmt.where(CognitiveCard.status == status)
    if days_back is not None:
        stmt = stmt.where(CognitiveCard.created_at >= utc_now() - timedelta(days=days_back))

    cards = list(db.scalars(stmt.order_by(CognitiveCard.created_at.desc())))

    if topic:
        cards = [card for card in cards if topic in (card.metadata_json or {}).get("topics", [])]
    if person:
        cards = [card for card in cards if person in (card.metadata_json or {}).get("people", [])]

    return cards


def update_card(db: Session, card_id: uuid.UUID, payload: CognitiveCardUpdate) -> CognitiveCard | None:
    card = get_card(db, card_id)
    if card is None:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(card, key, value)
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


def close_card(db: Session, card_id: uuid.UUID) -> CognitiveCard | None:
    card = get_card(db, card_id)
    if card is None:
        return None
    card.status = CardStatus.closed
    db.add(card)
    db.commit()
    db.refresh(card)
    return card
