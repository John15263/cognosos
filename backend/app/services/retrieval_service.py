from __future__ import annotations

import math
import uuid
from datetime import timedelta
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import utc_now
from backend.app.models.db_models import CognitiveCard
from backend.app.models.enums import CardModuleType, CardStatus
from backend.app.models.schemas import SearchResult


def retrieve_similar_cards(
    db: Session,
    query_embedding: list[float],
    module_types: list[CardModuleType] | None = None,
    statuses: list[CardStatus] | None = None,
    days_back: int = 90,
    limit: int = 8,
    min_similarity: float = 0.70,
    exclude_entry_id: uuid.UUID | str | None = None,
) -> list[SearchResult]:
    stmt = select(CognitiveCard).where(
        CognitiveCard.embedding.is_not(None),
        CognitiveCard.created_at >= utc_now() - timedelta(days=days_back),
    )

    if exclude_entry_id is not None:
        stmt = stmt.where(CognitiveCard.entry_id != uuid.UUID(str(exclude_entry_id)))
    if module_types:
        stmt = stmt.where(CognitiveCard.module_type.in_(module_types))
    if statuses:
        stmt = stmt.where(CognitiveCard.status.in_(statuses))

    ranked: list[tuple[float, CognitiveCard]] = []
    for card in db.scalars(stmt):
        similarity = cosine_similarity(query_embedding, card.embedding or [])
        if similarity >= min_similarity:
            ranked.append((similarity, card))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [
        SearchResult(
            card_id=card.id,
            similarity=round(similarity, 6),
            module_type=card.module_type,
            status=card.status,
            summary=card.summary,
            created_at=card.created_at,
        )
        for similarity, card in ranked[:limit]
    ]


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_values = list(left)
    right_values = list(right)
    if not left_values or not right_values or len(left_values) != len(right_values):
        return 0.0
    dot = sum(a * b for a, b in zip(left_values, right_values, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left_values))
    right_norm = math.sqrt(sum(b * b for b in right_values))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)

