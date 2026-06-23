from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.schemas import RawEntryCreate
from backend.app.services.entry_service import process_entry


def run_ingestion_graph(db: Session, payload: RawEntryCreate):
    """Phase 3-compatible wrapper; business logic lives in services."""

    return process_entry(db, payload)

