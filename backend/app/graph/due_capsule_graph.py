from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.services.trigger_service import create_due_capsule_triggers


def run_due_capsule_graph(db: Session):
    """Find due capsules, create check_review triggers, and mark capsules triggered."""

    return create_due_capsule_triggers(db)

