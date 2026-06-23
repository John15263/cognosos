from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.schemas import FlowSessionCreate, FlowSessionRead, FlowSessionResponse
from backend.app.services.flow_session_service import create_flow_session, list_flow_sessions

router = APIRouter(prefix="/flow-sessions", tags=["flow sessions"])


@router.post("", response_model=FlowSessionResponse)
def create_session(payload: FlowSessionCreate, db: Session = Depends(get_db)) -> FlowSessionResponse:
    return create_flow_session(db, payload)


@router.get("", response_model=list[FlowSessionRead])
def read_sessions(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db)) -> list[FlowSessionRead]:
    sessions = list_flow_sessions(db, limit=limit)
    return [FlowSessionRead.model_validate(session) for session in sessions]

