from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.enums import TimeCapsuleStatus
from backend.app.models.schemas import TimeCapsuleRead, TimeCapsuleResolveRequest, TriggerEventRead
from backend.app.services.time_capsule_service import dismiss_time_capsule, list_time_capsules, resolve_time_capsule
from backend.app.services.trigger_service import create_due_capsule_triggers

router = APIRouter(prefix="/time-capsules", tags=["time capsules"])


@router.get("", response_model=list[TimeCapsuleRead])
def read_time_capsules(
    status: TimeCapsuleStatus | None = None,
    db: Session = Depends(get_db),
) -> list[TimeCapsuleRead]:
    capsules = list_time_capsules(db, status=status)
    return [TimeCapsuleRead.model_validate(capsule) for capsule in capsules]


@router.get("/due")
def discover_due_time_capsules(db: Session = Depends(get_db)) -> dict[str, list[TimeCapsuleRead] | list[TriggerEventRead]]:
    capsules, events = create_due_capsule_triggers(db)
    return {
        "time_capsules": [TimeCapsuleRead.model_validate(capsule) for capsule in capsules],
        "trigger_events": [TriggerEventRead.model_validate(event) for event in events],
    }


@router.post("/{capsule_id}/resolve", response_model=TimeCapsuleRead)
def resolve_capsule(
    capsule_id: uuid.UUID,
    payload: TimeCapsuleResolveRequest | None = None,
    db: Session = Depends(get_db),
) -> TimeCapsuleRead:
    capsule = resolve_time_capsule(db, capsule_id, notes=payload.resolution_notes if payload else None)
    if capsule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time capsule not found")
    return TimeCapsuleRead.model_validate(capsule)


@router.post("/{capsule_id}/dismiss", response_model=TimeCapsuleRead)
def dismiss_capsule(
    capsule_id: uuid.UUID,
    payload: TimeCapsuleResolveRequest | None = None,
    db: Session = Depends(get_db),
) -> TimeCapsuleRead:
    capsule = dismiss_time_capsule(db, capsule_id, notes=payload.resolution_notes if payload else None)
    if capsule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Time capsule not found")
    return TimeCapsuleRead.model_validate(capsule)
