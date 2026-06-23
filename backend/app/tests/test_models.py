from backend.app.db.base import Base
from backend.app.models.db_models import CognitiveCard
from backend.app.models.enums import CardModuleType


def test_phase_1_tables_are_registered():
    assert {
        "raw_entries",
        "cognitive_cards",
        "time_capsules",
        "trigger_events",
        "module_runs",
    }.issubset(Base.metadata.tables.keys())


def test_card_uses_metadata_json_column_name():
    assert "metadata_json" in CognitiveCard.__table__.columns
    assert "metadata" not in CognitiveCard.__table__.columns


def test_card_score_constraints_accept_valid_model(db_session):
    card = CognitiveCard(
        module_type=CardModuleType.general,
        summary="summary",
        content="content",
        content_for_embedding="content",
        emotion_score=5,
        importance_score=6,
        urgency_score=7,
        metadata_json={"topics": ["phase 1"]},
    )

    db_session.add(card)
    db_session.commit()

    assert card.id is not None
    assert card.metadata_json == {"topics": ["phase 1"]}

