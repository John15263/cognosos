from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.schemas import EntryCreateResponse, RawEntryCreate, RawEntryRead
from backend.app.services.entry_service import get_raw_entry, process_entry

router = APIRouter(prefix="/entries", tags=["entries"])
logger = logging.getLogger(__name__)


@router.post("", response_model=EntryCreateResponse, status_code=status.HTTP_201_CREATED)
def create_entry(payload: RawEntryCreate, db: Session = Depends(get_db)) -> EntryCreateResponse:
    try:
        return process_entry(db, payload)
    except Exception as exc:
        logger.exception("Failed to process entry")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process entry") from exc


@router.get("/{entry_id}", response_model=RawEntryRead)
def read_entry(entry_id: uuid.UUID, db: Session = Depends(get_db)) -> RawEntryRead:
    entry = get_raw_entry(db, entry_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return RawEntryRead.model_validate(entry)
