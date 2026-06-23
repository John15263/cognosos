from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.enums import TriggerEventStatus
from backend.app.models.schemas import TriggerEventRead
from backend.app.services.trigger_service import list_trigger_events, update_trigger_status

router = APIRouter(prefix="/triggers", tags=["triggers"])


@router.get("", response_model=list[TriggerEventRead])
def read_triggers(
    status_filter: TriggerEventStatus | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[TriggerEventRead]:
    events = list_trigger_events(db, status=status_filter)
    return [TriggerEventRead.model_validate(event) for event in events]


@router.post("/{trigger_id}/accept", response_model=TriggerEventRead)
def accept_trigger(trigger_id: uuid.UUID, db: Session = Depends(get_db)) -> TriggerEventRead:
    event = update_trigger_status(db, trigger_id, TriggerEventStatus.accepted)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trigger not found")
    return TriggerEventRead.model_validate(event)


@router.post("/{trigger_id}/dismiss", response_model=TriggerEventRead)
def dismiss_trigger(trigger_id: uuid.UUID, db: Session = Depends(get_db)) -> TriggerEventRead:
    event = update_trigger_status(db, trigger_id, TriggerEventStatus.dismissed)
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trigger not found")
    return TriggerEventRead.model_validate(event)

