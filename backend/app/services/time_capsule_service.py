from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import utc_now
from backend.app.models.db_models import TimeCapsule
from backend.app.models.enums import TimeCapsuleStatus
from backend.app.models.schemas import TimeCapsuleCreate


def create_time_capsule(db: Session, payload: TimeCapsuleCreate) -> TimeCapsule:
    capsule = TimeCapsule(**payload.model_dump())
    db.add(capsule)
    db.flush()
    return capsule


def list_time_capsules(db: Session, status: TimeCapsuleStatus | None = None) -> list[TimeCapsule]:
    stmt = select(TimeCapsule)
    if status is not None:
        stmt = stmt.where(TimeCapsule.status == status)
    return list(db.scalars(stmt.order_by(TimeCapsule.trigger_at.asc())))


def get_due_time_capsules(db: Session) -> list[TimeCapsule]:
    return list(
        db.scalars(
            select(TimeCapsule)
            .where(TimeCapsule.status == TimeCapsuleStatus.pending, TimeCapsule.trigger_at <= utc_now())
            .order_by(TimeCapsule.trigger_at.asc())
        )
    )


def resolve_time_capsule(db: Session, capsule_id: uuid.UUID, notes: str | None = None) -> TimeCapsule | None:
    capsule = db.get(TimeCapsule, capsule_id)
    if capsule is None:
        return None
    capsule.status = TimeCapsuleStatus.resolved
    capsule.resolution_notes = notes
    capsule.resolved_at = utc_now()
    db.add(capsule)
    db.commit()
    db.refresh(capsule)
    return capsule


def dismiss_time_capsule(db: Session, capsule_id: uuid.UUID, notes: str | None = None) -> TimeCapsule | None:
    capsule = db.get(TimeCapsule, capsule_id)
    if capsule is None:
        return None
    capsule.status = TimeCapsuleStatus.dismissed
    capsule.resolution_notes = notes
    capsule.resolved_at = utc_now()
    db.add(capsule)
    db.commit()
    db.refresh(capsule)
    return capsule
