from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.db_models import RawEntry
from backend.app.models.enums import CardStatus, ProcessingStatus
from backend.app.models.schemas import CognitiveCardCreate, EntryCreateResponse, RawEntryCreate
from backend.app.services.card_service import create_card
from backend.app.services.embedding_service import embed_text
from backend.app.services.llm_service import get_llm_provider
from backend.app.services.retrieval_service import retrieve_similar_cards
from backend.app.services.trigger_service import create_trigger_event, plan_trigger_decisions


def create_raw_entry(db: Session, payload: RawEntryCreate) -> RawEntry:
    entry = RawEntry(
        content=payload.content,
        source=payload.source,
        processing_status=ProcessingStatus.received,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_raw_entry(db: Session, entry_id: uuid.UUID) -> RawEntry | None:
    return db.get(RawEntry, entry_id)


def list_raw_entries(db: Session) -> list[RawEntry]:
    return list(db.scalars(select(RawEntry).order_by(RawEntry.created_at.desc())))


def process_entry(db: Session, payload: RawEntryCreate) -> EntryCreateResponse:
    entry = create_raw_entry(db, payload)
    created_cards = []
    trigger_events = []
    llm_provider = get_llm_provider()

    try:
        extracted = llm_provider.extract_cards(payload.content)

        for extracted_card in extracted.cards:
            vector, model_name, dimension = embed_text(extracted_card.content_for_embedding)
            card_payload = CognitiveCardCreate(
                **extracted_card.model_dump(exclude={"entry_id", "embedding", "embedding_model", "embedding_dim"}),
                entry_id=entry.id,
                embedding=vector,
                embedding_model=model_name,
                embedding_dim=dimension,
            )
            created_cards.append(create_card(db, card_payload))

        db.flush()

        for card in created_cards:
            historical_context = retrieve_similar_cards(
                db,
                query_embedding=card.embedding or [],
                statuses=[CardStatus.open, CardStatus.stalled, CardStatus.closed],
                days_back=90,
                limit=12,
                min_similarity=0.35,
                exclude_entry_id=entry.id,
            )
            candidates = plan_trigger_decisions(db, card, historical_context)
            decisions = llm_provider.judge_triggers(candidates)
            for decision in decisions:
                event = create_trigger_event(db, card, decision)
                if event is not None:
                    trigger_events.append(event)

        entry.processing_status = ProcessingStatus.processed
        db.add(entry)
        db.commit()
        db.refresh(entry)
        for card in created_cards:
            db.refresh(card)
        for event in trigger_events:
            db.refresh(event)
        return EntryCreateResponse(entry_id=entry.id, cards=created_cards, trigger_events=trigger_events, time_capsules=[])
    except Exception as exc:
        db.rollback()
        failed_entry = db.get(RawEntry, entry.id)
        if failed_entry is not None:
            failed_entry.processing_status = ProcessingStatus.failed
            failed_entry.error_message = str(exc)
            db.add(failed_entry)
            db.commit()
        raise
