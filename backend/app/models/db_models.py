from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from backend.app.db.base import Base, GUID, VectorType, utc_now
from backend.app.models.enums import (
    CardModuleType,
    CardStatus,
    ModuleRunStatus,
    ObsidianObjectType,
    PrivacyLevel,
    ProcessingStatus,
    RawEntrySource,
    TimeCapsuleActionType,
    TimeCapsuleStatus,
    TriggerEventStatus,
    TriggerModuleType,
    WritingSessionMode,
    WritingSessionStatus,
)

JsonType = JSON().with_variant(JSONB, "postgresql")


def enum_type(enum_cls: type, name: str) -> Enum:
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda values: [item.value for item in values],
        native_enum=False,
        validate_strings=True,
    )


class TimestampMixin:
    created_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )
    updated_at: Mapped[Any] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False,
    )


class RawEntry(TimestampMixin, Base):
    __tablename__ = "raw_entries"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[RawEntrySource] = mapped_column(
        enum_type(RawEntrySource, "raw_entry_source"),
        nullable=False,
        default=RawEntrySource.text,
        server_default=RawEntrySource.text.value,
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        enum_type(ProcessingStatus, "processing_status"),
        nullable=False,
        default=ProcessingStatus.received,
        server_default=ProcessingStatus.received.value,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    cards: Mapped[list[CognitiveCard]] = relationship(
        back_populates="entry",
        cascade="all, delete-orphan",
    )


class CognitiveCard(TimestampMixin, Base):
    __tablename__ = "cognitive_cards"
    __table_args__ = (
        CheckConstraint("emotion_score IS NULL OR (emotion_score >= 0 AND emotion_score <= 10)", name="ck_cards_emotion_score"),
        CheckConstraint("importance_score IS NULL OR (importance_score >= 0 AND importance_score <= 10)", name="ck_cards_importance_score"),
        CheckConstraint("urgency_score IS NULL OR (urgency_score >= 0 AND urgency_score <= 10)", name="ck_cards_urgency_score"),
        Index("idx_cards_created_at", "created_at"),
        Index("idx_cards_status", "status"),
        Index("idx_cards_module_type", "module_type"),
        Index("idx_cards_source_session_id", "source_session_id"),
        Index("idx_cards_source_stage_id", "source_stage_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    entry_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("raw_entries.id"), nullable=True)
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("writing_sessions.id"), nullable=True)
    source_stage_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("writing_session_stages.id"), nullable=True)

    module_type: Mapped[CardModuleType] = mapped_column(enum_type(CardModuleType, "card_module_type"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_for_embedding: Mapped[str] = mapped_column(Text, nullable=False)

    embedding: Mapped[list[float] | None] = mapped_column(VectorType(1024), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_dim: Mapped[int] = mapped_column(Integer, nullable=False, default=1024, server_default="1024")

    emotion_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    importance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    urgency_score: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[CardStatus] = mapped_column(
        enum_type(CardStatus, "card_status"),
        nullable=False,
        default=CardStatus.open,
        server_default=CardStatus.open.value,
    )
    privacy_level: Mapped[PrivacyLevel] = mapped_column(
        enum_type(PrivacyLevel, "privacy_level"),
        nullable=False,
        default=PrivacyLevel.private,
        server_default=PrivacyLevel.private.value,
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict, server_default=text("'{}'"))

    entry: Mapped[RawEntry | None] = relationship(back_populates="cards")
    time_capsules: Mapped[list[TimeCapsule]] = relationship(back_populates="card")
    trigger_events: Mapped[list[TriggerEvent]] = relationship(back_populates="current_card")


class TimeCapsule(TimestampMixin, Base):
    __tablename__ = "time_capsules"
    __table_args__ = (
        Index("idx_time_capsules_trigger_at", "trigger_at"),
        Index("idx_time_capsules_status", "status"),
        Index("idx_time_capsules_source_session_id", "source_session_id"),
        Index("idx_time_capsules_source_stage_id", "source_stage_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    card_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("cognitive_cards.id"), nullable=True)
    source_session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("writing_sessions.id"), nullable=True)
    source_stage_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("writing_session_stages.id"), nullable=True)
    action_type: Mapped[TimeCapsuleActionType] = mapped_column(
        enum_type(TimeCapsuleActionType, "time_capsule_action_type"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_at: Mapped[Any] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[TimeCapsuleStatus] = mapped_column(
        enum_type(TimeCapsuleStatus, "time_capsule_status"),
        nullable=False,
        default=TimeCapsuleStatus.pending,
        server_default=TimeCapsuleStatus.pending.value,
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)

    card: Mapped[CognitiveCard | None] = relationship(back_populates="time_capsules")


class TriggerEvent(TimestampMixin, Base):
    __tablename__ = "trigger_events"
    __table_args__ = (
        CheckConstraint("intervention_level >= 0 AND intervention_level <= 3", name="ck_trigger_events_intervention_level"),
        CheckConstraint("confidence IS NULL OR (confidence >= 0 AND confidence <= 1)", name="ck_trigger_events_confidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    triggered_module: Mapped[TriggerModuleType] = mapped_column(
        enum_type(TriggerModuleType, "trigger_module_type"),
        nullable=False,
    )
    current_card_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("cognitive_cards.id"), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_card_ids: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list, server_default=text("'[]'"))
    evidence: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict, server_default=text("'{}'"))
    intervention_level: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric, nullable=True)
    status: Mapped[TriggerEventStatus] = mapped_column(
        enum_type(TriggerEventStatus, "trigger_event_status"),
        nullable=False,
        default=TriggerEventStatus.suggested,
        server_default=TriggerEventStatus.suggested.value,
    )

    current_card: Mapped[CognitiveCard | None] = relationship(back_populates="trigger_events")
    module_runs: Mapped[list[ModuleRun]] = relationship(back_populates="trigger_event")


class ModuleRun(TimestampMixin, Base):
    __tablename__ = "module_runs"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    module_type: Mapped[TriggerModuleType] = mapped_column(enum_type(TriggerModuleType, "module_run_type"), nullable=False)
    trigger_event_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("trigger_events.id"), nullable=True)
    input_card_ids: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list, server_default=text("'[]'"))
    answers: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict, server_default=text("'{}'"))
    output: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict, server_default=text("'{}'"))
    created_card_ids: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list, server_default=text("'[]'"))
    created_time_capsule_ids: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list, server_default=text("'[]'"))
    status: Mapped[ModuleRunStatus] = mapped_column(
        enum_type(ModuleRunStatus, "module_run_status"),
        nullable=False,
        default=ModuleRunStatus.completed,
        server_default=ModuleRunStatus.completed.value,
    )

    trigger_event: Mapped[TriggerEvent | None] = relationship(back_populates="module_runs")


class WritingSession(TimestampMixin, Base):
    __tablename__ = "writing_sessions"
    __table_args__ = (
        Index("idx_writing_sessions_status", "status"),
        Index("idx_writing_sessions_started_at", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    prompt_id: Mapped[str] = mapped_column(String(80), nullable=False)
    prompt_title: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_cues: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list, server_default=text("'[]'"))
    mode: Mapped[WritingSessionMode] = mapped_column(
        enum_type(WritingSessionMode, "writing_session_mode"),
        nullable=False,
        default=WritingSessionMode.hard,
        server_default=WritingSessionMode.hard.value,
    )
    status: Mapped[WritingSessionStatus] = mapped_column(
        enum_type(WritingSessionStatus, "writing_session_status"),
        nullable=False,
        default=WritingSessionStatus.started,
        server_default=WritingSessionStatus.started.value,
    )
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    idle_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    final_word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    interruption_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    structured_payload: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict, server_default=text("'{}'"))
    pipeline_version: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision_stage_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_entry_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("raw_entries.id"), nullable=True)
    started_at: Mapped[Any] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    ended_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stages: Mapped[list[WritingSessionStage]] = relationship(
        back_populates="writing_session",
        cascade="all, delete-orphan",
        order_by="WritingSessionStage.stage_order",
    )


class WritingSessionStage(TimestampMixin, Base):
    __tablename__ = "writing_session_stages"
    __table_args__ = (
        Index("idx_writing_session_stages_session_id", "writing_session_id"),
        Index("idx_writing_session_stages_stage_id", "stage_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    writing_session_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("writing_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage_id: Mapped[str] = mapped_column(String(80), nullable=False)
    stage_order: Mapped[int] = mapped_column(Integer, nullable=False)
    module_type: Mapped[CardModuleType] = mapped_column(enum_type(CardModuleType, "card_module_type"), nullable=False)

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    ghost_starter: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    status: Mapped[str] = mapped_column(String(40), nullable=False, default="completed", server_default="completed")
    idle_timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    interruption_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    started_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Any | None] = mapped_column(DateTime(timezone=True), nullable=True)

    nudges_shown: Mapped[list[str]] = mapped_column(JsonType, nullable=False, default=list, server_default=text("'[]'"))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JsonType, nullable=False, default=dict, server_default=text("'{}'"))
    created_card_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    writing_session: Mapped[WritingSession] = relationship(back_populates="stages")


class ObsidianLink(TimestampMixin, Base):
    __tablename__ = "obsidian_links"
    __table_args__ = (
        Index("idx_obsidian_links_object", "object_type", "object_id"),
        Index("idx_obsidian_links_note_path", "note_path"),
    )

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    object_type: Mapped[ObsidianObjectType] = mapped_column(enum_type(ObsidianObjectType, "obsidian_object_type"), nullable=False)
    object_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    note_path: Mapped[str] = mapped_column(Text, nullable=False)
    block_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
