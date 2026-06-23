from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.enums import CardModuleType, CardStatus
from backend.app.models.schemas import CognitiveCardRead, CognitiveCardUpdate
from backend.app.services.card_service import close_card, get_card, list_cards, update_card

router = APIRouter(prefix="/cards", tags=["cards"])


@router.get("", response_model=list[CognitiveCardRead])
def read_cards(
    module_type: CardModuleType | None = None,
    status: CardStatus | None = None,
    topic: str | None = Query(default=None, min_length=1),
    person: str | None = Query(default=None, min_length=1),
    days_back: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> list[CognitiveCardRead]:
    cards = list_cards(
        db,
        module_type=module_type,
        status=status,
        topic=topic,
        person=person,
        days_back=days_back,
    )
    return [CognitiveCardRead.model_validate(card) for card in cards]


@router.get("/{card_id}", response_model=CognitiveCardRead)
def read_card(card_id: uuid.UUID, db: Session = Depends(get_db)) -> CognitiveCardRead:
    card = get_card(db, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return CognitiveCardRead.model_validate(card)


@router.patch("/{card_id}", response_model=CognitiveCardRead)
def patch_card(card_id: uuid.UUID, payload: CognitiveCardUpdate, db: Session = Depends(get_db)) -> CognitiveCardRead:
    card = update_card(db, card_id, payload)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return CognitiveCardRead.model_validate(card)


@router.post("/{card_id}/close", response_model=CognitiveCardRead)
def close_card_endpoint(card_id: uuid.UUID, db: Session = Depends(get_db)) -> CognitiveCardRead:
    card = close_card(db, card_id)
    if card is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    return CognitiveCardRead.model_validate(card)
