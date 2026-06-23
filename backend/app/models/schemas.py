from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from backend.app.models.enums import (
    CardModuleType,
    CardStatus,
    ModuleRunStatus,
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


class ApiSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")


class RawEntryCreate(ApiSchema):
    content: str = Field(min_length=1)
    source: RawEntrySource = RawEntrySource.text


class RawEntryRead(ApiSchema):
    id: uuid.UUID
    content: str
    source: RawEntrySource
    processing_status: ProcessingStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class CognitiveCardCreate(ApiSchema):
    entry_id: uuid.UUID | None = None
    source_session_id: uuid.UUID | None = None
    source_stage_id: uuid.UUID | None = None
    module_type: CardModuleType
    title: str | None = None
    summary: str = Field(min_length=1)
    content: str = Field(min_length=1)
    content_for_embedding: str = Field(min_length=1)
    embedding: list[float] | None = None
    embedding_model: str | None = None
    embedding_dim: int = 1024
    emotion_score: int | None = Field(default=None, ge=0, le=10)
    importance_score: int | None = Field(default=None, ge=0, le=10)
    urgency_score: int | None = Field(default=None, ge=0, le=10)
    status: CardStatus = CardStatus.open
    privacy_level: PrivacyLevel = PrivacyLevel.private
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class CognitiveCardUpdate(ApiSchema):
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    content_for_embedding: str | None = None
    emotion_score: int | None = Field(default=None, ge=0, le=10)
    importance_score: int | None = Field(default=None, ge=0, le=10)
    urgency_score: int | None = Field(default=None, ge=0, le=10)
    status: CardStatus | None = None
    privacy_level: PrivacyLevel | None = None
    metadata_json: dict[str, Any] | None = None


class CognitiveCardRead(ApiSchema):
    id: uuid.UUID
    entry_id: uuid.UUID | None
    source_session_id: uuid.UUID | None
    source_stage_id: uuid.UUID | None
    module_type: CardModuleType
    title: str | None
    summary: str
    content: str
    content_for_embedding: str
    embedding: list[float] | None
    embedding_model: str | None
    embedding_dim: int
    emotion_score: int | None
    importance_score: int | None
    urgency_score: int | None
    status: CardStatus
    privacy_level: PrivacyLevel
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ExtractorCard(CognitiveCardCreate):
    pass


class ExtractorOutput(ApiSchema):
    cards: list[ExtractorCard]


class SearchRequest(ApiSchema):
    query: str = Field(min_length=1)
    module_types: list[CardModuleType] | None = None
    statuses: list[CardStatus] | None = None
    days_back: int = Field(default=90, ge=1)
    limit: int = Field(default=8, ge=1, le=50)
    min_similarity: float = Field(default=0.70, ge=0, le=1)


class SearchResult(ApiSchema):
    card_id: uuid.UUID
    similarity: float
    module_type: CardModuleType
    status: CardStatus
    summary: str
    created_at: datetime


class SearchResponse(ApiSchema):
    results: list[SearchResult]


class TriggerEventRead(ApiSchema):
    id: uuid.UUID
    triggered_module: TriggerModuleType
    current_card_id: uuid.UUID | None
    reason: str
    evidence_card_ids: list[str]
    evidence: dict[str, Any]
    intervention_level: int
    confidence: float | None
    status: TriggerEventStatus
    created_at: datetime
    updated_at: datetime


class TriggerDecision(ApiSchema):
    triggered: bool
    triggered_module: TriggerModuleType | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str | None = None
    evidence_card_ids: list[str] = Field(default_factory=list)
    intervention_level: int | None = Field(default=None, ge=0, le=3)
    next_question: str | None = None


class TimeCapsuleCreate(ApiSchema):
    card_id: uuid.UUID | None = None
    source_session_id: uuid.UUID | None = None
    source_stage_id: uuid.UUID | None = None
    action_type: TimeCapsuleActionType
    title: str = Field(min_length=1)
    description: str | None = None
    trigger_at: datetime


class TimeCapsuleRead(ApiSchema):
    id: uuid.UUID
    card_id: uuid.UUID | None
    source_session_id: uuid.UUID | None
    source_stage_id: uuid.UUID | None
    action_type: TimeCapsuleActionType
    title: str
    description: str | None
    trigger_at: datetime
    status: TimeCapsuleStatus
    resolution_notes: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None


class ModuleRunRequest(ApiSchema):
    trigger_event_id: uuid.UUID | None = None
    input_card_ids: list[uuid.UUID] = Field(default_factory=list)
    time_capsule_id: uuid.UUID | None = None
    answers: dict[str, Any] = Field(default_factory=dict)


class ModuleRunRead(ApiSchema):
    id: uuid.UUID
    module_type: TriggerModuleType
    trigger_event_id: uuid.UUID | None
    input_card_ids: list[str]
    answers: dict[str, Any]
    output: dict[str, Any]
    created_card_ids: list[str]
    created_time_capsule_ids: list[str]
    status: ModuleRunStatus
    created_at: datetime
    updated_at: datetime


class TimeCapsuleResolveRequest(ApiSchema):
    resolution_notes: str | None = None


class EntryCreateResponse(ApiSchema):
    entry_id: uuid.UUID
    cards: list[CognitiveCardRead] = Field(default_factory=list)
    trigger_events: list[TriggerEventRead] = Field(default_factory=list)
    time_capsules: list[TimeCapsuleRead] = Field(default_factory=list)


class FlowSessionStageCreate(ApiSchema):
    stage_id: str = Field(min_length=1, max_length=80)
    stage_order: int = Field(ge=1)
    module_type: CardModuleType
    title: str | None = None
    prompt_label: str | None = None
    ghost_starter: str | None = None
    content: str = ""
    word_count: int = Field(default=0, ge=0)
    status: str = Field(default="completed", max_length=40)
    idle_timeout_seconds: int | None = Field(default=None, ge=2)
    interruption_count: int = Field(default=0, ge=0)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    nudges_shown: list[str] = Field(default_factory=list)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class FlowSessionCreate(ApiSchema):
    prompt_id: str = Field(min_length=1, max_length=80)
    prompt_title: str = Field(min_length=1)
    prompt_cues: list[str] = Field(default_factory=list)
    content: str = Field(default="")
    compiled_markdown: str | None = None
    mode: WritingSessionMode = WritingSessionMode.hard
    status: WritingSessionStatus
    duration_seconds: int = Field(default=300, ge=10)
    idle_timeout_seconds: int = Field(default=7, ge=2)
    final_word_count: int = Field(default=0, ge=0)
    interruption_count: int = Field(default=0, ge=0)
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    pipeline_version: str | None = None
    decision_stage_enabled: bool = False
    stages: list[FlowSessionStageCreate] = Field(default_factory=list)


class FlowSessionStageRead(ApiSchema):
    id: uuid.UUID
    writing_session_id: uuid.UUID
    stage_id: str
    stage_order: int
    module_type: CardModuleType
    title: str | None
    prompt_label: str | None
    ghost_starter: str | None
    content: str
    word_count: int
    status: str
    idle_timeout_seconds: int | None
    interruption_count: int
    started_at: datetime | None
    completed_at: datetime | None
    nudges_shown: list[str]
    metadata_json: dict[str, Any]
    created_card_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class FlowSessionRead(ApiSchema):
    id: uuid.UUID
    prompt_id: str
    prompt_title: str
    prompt_cues: list[str]
    mode: WritingSessionMode
    status: WritingSessionStatus
    duration_seconds: int
    idle_timeout_seconds: int
    final_word_count: int
    interruption_count: int
    structured_payload: dict[str, Any]
    pipeline_version: str | None
    decision_stage_enabled: bool
    content_hash: str | None
    note_path: str | None
    raw_entry_id: uuid.UUID | None
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime
    stages: list[FlowSessionStageRead] = Field(default_factory=list)


class FlowSessionResponse(ApiSchema):
    session: FlowSessionRead
    entry: EntryCreateResponse | None = None
