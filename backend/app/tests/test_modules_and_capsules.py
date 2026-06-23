from datetime import timedelta

from backend.app.db.base import utc_now
from backend.app.models.db_models import TimeCapsule
from backend.app.models.enums import TimeCapsuleActionType, TimeCapsuleStatus


def test_scaffolding_module_creates_card_capsule_and_module_run(client):
    response = client.post(
        "/modules/scaffolding/run",
        json={
            "answers": {
                "我要解决的问题是": "把 CognosOS 做成最小可用 demo",
                "10 分钟内的最小下一步是什么": "写一个 POST /entries 示例",
                "我什么时候 check": (utc_now() + timedelta(days=1)).isoformat(),
            }
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["module_type"] == "scaffolding"
    assert len(payload["created_card_ids"]) == 1
    assert len(payload["created_time_capsule_ids"]) == 1


def test_due_capsule_creates_check_review_trigger(client, db_session):
    capsule = TimeCapsule(
        action_type=TimeCapsuleActionType.review_scaffold,
        title="Review scaffold",
        trigger_at=utc_now() - timedelta(minutes=1),
        status=TimeCapsuleStatus.pending,
    )
    db_session.add(capsule)
    db_session.commit()

    response = client.get("/time-capsules/due")

    assert response.status_code == 200
    payload = response.json()
    assert payload["time_capsules"][0]["status"] == "triggered"
    assert payload["trigger_events"][0]["triggered_module"] == "check_review"

