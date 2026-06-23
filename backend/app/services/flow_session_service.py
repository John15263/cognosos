from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import utc_now
from backend.app.models.db_models import WritingSession
from backend.app.models.enums import ObsidianObjectType, RawEntrySource, WritingSessionStatus
from backend.app.models.schemas import EntryCreateResponse, FlowSessionCreate, FlowSessionResponse, RawEntryCreate
from backend.app.services.breakthrough_canvas_service import create_breakthrough_canvas_session
from backend.app.services.entry_service import process_entry
from backend.app.services.obsidian_service import append_flow_capture_to_daily_note, content_hash, create_obsidian_link


def create_flow_session(db: Session, payload: FlowSessionCreate) -> FlowSessionResponse:
    if payload.stages:
        return create_breakthrough_canvas_session(db, payload)

    content = payload.content or payload.compiled_markdown or ""
    structured_payload = dict(payload.structured_payload)
    if payload.compiled_markdown:
        structured_payload.setdefault("client_preview_markdown", payload.compiled_markdown)
    saved_content_hash = content_hash(content) if payload.status == WritingSessionStatus.completed else None
    session = WritingSession(
        prompt_id=payload.prompt_id,
        prompt_title=payload.prompt_title,
        prompt_cues=payload.prompt_cues,
        mode=payload.mode,
        status=payload.status,
        duration_seconds=payload.duration_seconds,
        idle_timeout_seconds=payload.idle_timeout_seconds,
        final_word_count=payload.final_word_count,
        interruption_count=payload.interruption_count,
        structured_payload=structured_payload,
        pipeline_version=payload.pipeline_version,
        decision_stage_enabled=payload.decision_stage_enabled,
        content_hash=saved_content_hash,
        started_at=utc_now(),
        ended_at=utc_now(),
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    entry_response: EntryCreateResponse | None = None
    if payload.status == WritingSessionStatus.completed and content.strip():
        note_path, hash_value = append_flow_capture_to_daily_note(
            prompt_title=payload.prompt_title,
            prompt_cues=payload.prompt_cues,
            content=content,
            session_id=session.id,
            created_at=session.ended_at,
        )
        entry_response = process_entry(db, RawEntryCreate(content=content, source=RawEntrySource.text))
        session.note_path = note_path
        session.raw_entry_id = entry_response.entry_id
        session.content_hash = hash_value
        db.add(session)
        create_obsidian_link(db, ObsidianObjectType.writing_session, session.id, note_path, hash_value)
        create_obsidian_link(db, ObsidianObjectType.raw_entry, entry_response.entry_id, note_path, hash_value)
        for card in entry_response.cards:
            create_obsidian_link(db, ObsidianObjectType.cognitive_card, card.id, note_path)
        for event in entry_response.trigger_events:
            create_obsidian_link(db, ObsidianObjectType.trigger_event, event.id, note_path)
        db.commit()
        db.refresh(session)

    return FlowSessionResponse(session=session, entry=entry_response)


def list_flow_sessions(db: Session, limit: int = 20) -> list[WritingSession]:
    return list(db.scalars(select(WritingSession).order_by(WritingSession.created_at.desc()).limit(limit)))
