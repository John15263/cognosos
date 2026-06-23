from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.db.base import utc_now
from backend.app.models.db_models import CognitiveCard, ObsidianLink, TimeCapsule, WritingSessionStage
from backend.app.models.enums import ObsidianObjectType


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def append_flow_capture_to_daily_note(
    prompt_title: str,
    prompt_cues: list[str],
    content: str,
    session_id: uuid.UUID,
    created_at: datetime | None = None,
) -> tuple[str, str]:
    settings = get_settings()
    now = created_at or utc_now()
    date_name = now.strftime("%Y%m%d")
    relative_path = f"{settings.markdown_daily_folder}/{date_name}.md"
    vault = Path(settings.markdown_vault_path).expanduser().resolve()
    note_path = vault / relative_path
    note_path.parent.mkdir(parents=True, exist_ok=True)

    cue_lines = "\n".join(f"- {cue}" for cue in prompt_cues)
    block = f"""
## Flow Capture - {prompt_title}

```cognosos
session_id: {session_id}
captured_at: {now.isoformat()}
```

### Prompt

{cue_lines}

### Draft

{content.strip()}
"""
    hash_value = _append_session_block(note_path, block, "flow-capture", session_id)
    return relative_path, hash_value


def append_breakthrough_canvas_to_daily_note(
    session_id: uuid.UUID,
    pipeline_version: str | None,
    decision_stage_enabled: bool,
    stages: list[WritingSessionStage],
    cards: list[CognitiveCard],
    time_capsules: list[TimeCapsule],
    created_at: datetime | None = None,
    heading: str = "Breakthrough Canvas",
    mode: str = "breakthrough_canvas",
) -> tuple[str, str]:
    settings = get_settings()
    now = created_at or utc_now()
    date_name = now.strftime("%Y%m%d")
    relative_path = f"{settings.markdown_daily_folder}/{date_name}.md"
    vault = Path(settings.markdown_vault_path).expanduser().resolve()
    note_path = vault / relative_path
    note_path.parent.mkdir(parents=True, exist_ok=True)

    stage_blocks = "\n\n".join(_stage_projection(stage) for stage in stages)
    card_lines = "\n".join(_card_projection(card) for card in cards) or "- No cards created."
    capsule_lines = "\n".join(_capsule_projection(capsule) for capsule in time_capsules) or "- No time capsules created."
    block = f"""
## {heading}

```cognosos
session_id: {session_id}
captured_at: {now.isoformat()}
mode: {mode}
pipeline_version: {pipeline_version or "unknown"}
decision_stage_enabled: {str(decision_stage_enabled).lower()}
cards_created: {len(cards)}
time_capsules_created: {len(time_capsules)}
```

{stage_blocks}

### Created Objects

{card_lines}

{capsule_lines}
"""
    hash_value = _append_session_block(note_path, block, "flow-session", session_id)
    return relative_path, hash_value


def _append_session_block(note_path: Path, block: str, kind: str, session_id: uuid.UUID) -> str:
    start = f"<!-- cognosos:{kind}:start id={session_id} -->"
    end = f"<!-- cognosos:{kind}:end id={session_id} -->"
    wrapped = f"\n\n{start}\n{block.strip()}\n{end}\n"
    if note_path.exists() and start in note_path.read_text(encoding="utf-8"):
        return content_hash(wrapped)
    # ponytail: local single-user append; add a file lock if concurrent writers matter.
    with note_path.open("a", encoding="utf-8") as file:
        file.write(wrapped)
    return content_hash(wrapped)


def _stage_projection(stage: WritingSessionStage) -> str:
    label = stage.prompt_label or f"Phase {stage.stage_order} · {stage.title or stage.stage_id}"
    status = stage.status
    if status == "skipped":
        content = "_Skipped._"
    elif stage.content.strip():
        content = stage.content.strip()
    else:
        content = "_No text captured._"
    return f"### {label}\n\n{content}"


def _card_projection(card: CognitiveCard) -> str:
    return f"- Card `{card.module_type.value}`: `{card.id}`"


def _capsule_projection(capsule: TimeCapsule) -> str:
    return f"- Time Capsule `{capsule.action_type.value}`: `{capsule.id}` due {capsule.trigger_at.isoformat()}"


def create_obsidian_link(
    db: Session,
    object_type: ObsidianObjectType,
    object_id: uuid.UUID,
    note_path: str,
    hash_value: str | None = None,
) -> ObsidianLink:
    link = ObsidianLink(
        object_type=object_type,
        object_id=object_id,
        note_path=note_path,
        content_hash=hash_value,
    )
    db.add(link)
    db.flush()
    return link
