from enum import StrEnum


class RawEntrySource(StrEnum):
    text = "text"
    voice = "voice"
    import_ = "import"


class ProcessingStatus(StrEnum):
    received = "received"
    processed = "processed"
    failed = "failed"


class CardModuleType(StrEnum):
    free_write = "free_write"
    decision = "decision"
    gratitude = "gratitude"
    reciprocity = "reciprocity"
    scaffolding = "scaffolding"
    avsi = "avsi"
    future_self = "future_self"
    check_review = "check_review"
    task = "task"
    prediction = "prediction"
    insight = "insight"
    general = "general"


class CardStatus(StrEnum):
    open = "open"
    closed = "closed"
    archived = "archived"
    stalled = "stalled"
    waiting = "waiting"
    dismissed = "dismissed"


class PrivacyLevel(StrEnum):
    private = "private"
    sensitive = "sensitive"
    normal = "normal"
    public = "public"


class TimeCapsuleActionType(StrEnum):
    check_decision = "check_decision"
    return_kindness = "return_kindness"
    review_scaffold = "review_scaffold"
    review_future_self = "review_future_self"
    review_avsi_followup = "review_avsi_followup"
    review_prediction = "review_prediction"
    general_reminder = "general_reminder"


class TimeCapsuleStatus(StrEnum):
    pending = "pending"
    triggered = "triggered"
    resolved = "resolved"
    dismissed = "dismissed"


class TriggerModuleType(StrEnum):
    decision = "decision"
    scaffolding = "scaffolding"
    avsi = "avsi"
    future_self = "future_self"
    reciprocity = "reciprocity"
    check_review = "check_review"


class TriggerEventStatus(StrEnum):
    suggested = "suggested"
    accepted = "accepted"
    dismissed = "dismissed"
    completed = "completed"


class ModuleRunStatus(StrEnum):
    started = "started"
    completed = "completed"
    cancelled = "cancelled"
    failed = "failed"


class WritingSessionMode(StrEnum):
    hard = "hard"
    soft = "soft"
    training = "training"


class WritingSessionStatus(StrEnum):
    started = "started"
    completed = "completed"
    failed = "failed"
    aborted = "aborted"


class ObsidianObjectType(StrEnum):
    raw_entry = "raw_entry"
    cognitive_card = "cognitive_card"
    trigger_event = "trigger_event"
    time_capsule = "time_capsule"
    module_run = "module_run"
    writing_session = "writing_session"
