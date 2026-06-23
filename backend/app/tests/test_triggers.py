from backend.app.models.db_models import CognitiveCard
from backend.app.models.enums import CardModuleType, CardStatus, PrivacyLevel, TriggerModuleType
from backend.app.services.trigger_service import plan_trigger_decisions


def test_decision_entry_creates_decision_trigger(client):
    response = client.post("/entries", json={"content": "我决定明天先做最小 demo。", "source": "text"})

    assert response.status_code == 201
    triggers = response.json()["trigger_events"]
    assert any(trigger["triggered_module"] == "decision" for trigger in triggers)


def test_repeated_stuck_problem_creates_scaffolding_trigger(client):
    client.post("/entries", json={"content": "我卡住了，不知道怎么开始 agent 系统。", "source": "text"})
    client.post("/entries", json={"content": "agent 系统还是卡住，我不知道怎么开始。", "source": "text"})

    response = client.post("/entries", json={"content": "我又卡住了，agent 系统太复杂，无从下手。", "source": "text"})

    assert response.status_code == 201
    triggers = response.json()["trigger_events"]
    scaffolding = [trigger for trigger in triggers if trigger["triggered_module"] == "scaffolding"]
    assert scaffolding
    assert scaffolding[0]["intervention_level"] == 3
    assert len(scaffolding[0]["evidence_card_ids"]) >= 2


def test_repeated_high_emotion_creates_future_self_trigger(client):
    client.post("/entries", json={"content": "我很焦虑，agent 系统太复杂了。", "source": "text"})
    client.post("/entries", json={"content": "我很焦虑，agent 系统太复杂了。", "source": "text"})

    response = client.post("/entries", json={"content": "我又很焦虑，agent 系统太复杂了。", "source": "text"})

    assert response.status_code == 201
    triggers = response.json()["trigger_events"]
    assert any(trigger["triggered_module"] == "future_self" for trigger in triggers)


def test_repeated_topic_creates_avsi_trigger(client):
    client.post("/entries", json={"content": "我想理解 pgvector。", "source": "text"})
    client.post("/entries", json={"content": "我想搞懂 pgvector 的索引。", "source": "text"})

    response = client.post("/entries", json={"content": "我还想研究 pgvector 的相似搜索机制。", "source": "text"})

    assert response.status_code == 201
    triggers = response.json()["trigger_events"]
    assert any(trigger["triggered_module"] == "avsi" for trigger in triggers)


def test_repeated_gratitude_creates_reciprocity_trigger(client):
    client.post("/entries", json={"content": "感谢 Alex 今天帮了我。", "source": "text"})

    response = client.post("/entries", json={"content": "感谢 Alex 又支持了我。", "source": "text"})

    assert response.status_code == 201
    triggers = response.json()["trigger_events"]
    assert any(trigger["triggered_module"] == "reciprocity" for trigger in triggers)


def test_breakthrough_non_decision_stage_does_not_create_decision_trigger(db_session):
    card = CognitiveCard(
        module_type=CardModuleType.free_write,
        title="Noise",
        summary="我在想是否要继续做这个项目。",
        content="我在想是否要继续做这个项目。",
        content_for_embedding="free_write: 我在想是否要继续做这个项目。",
        embedding=[0.1] * 1024,
        embedding_model="mock",
        embedding_dim=1024,
        status=CardStatus.open,
        privacy_level=PrivacyLevel.private,
        metadata_json={"pipeline": "breakthrough_canvas", "stage_id": "mental_dump"},
    )

    decisions = plan_trigger_decisions(db_session, card, [])

    assert TriggerModuleType.decision not in {decision.triggered_module for decision in decisions}
