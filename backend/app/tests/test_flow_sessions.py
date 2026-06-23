from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from backend.app.models.db_models import RawEntry, WritingSessionStage
from backend.app.models.enums import CardModuleType, ProcessingStatus, TimeCapsuleActionType
from backend.app.services.obsidian_service import append_breakthrough_canvas_to_daily_note


def test_completed_flow_session_writes_obsidian_note_and_ingests(client, monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

    response = client.post(
        "/flow-sessions",
        json={
            "prompt_id": "daily-review",
            "prompt_title": "Daily Review",
            "prompt_cues": ["今天要感谢的三个人", "今天值得记录的时刻"],
            "content": "感谢 Alex 帮我推进 agent demo。今天值得记录的时刻是完成了 Flow Capture。",
            "mode": "hard",
            "status": "completed",
            "duration_seconds": 300,
            "idle_timeout_seconds": 7,
            "final_word_count": 36,
            "interruption_count": 0,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["note_path"].startswith("Calendar/")
    assert payload["session"]["raw_entry_id"]
    assert payload["entry"]["cards"]

    note = next((vault / "Calendar").glob("*.md"))
    text = note.read_text(encoding="utf-8")
    assert "Flow Capture - Daily Review" in text
    assert "感谢 Alex" in text


def test_completed_flow_session_accepts_cognosos_vault_alias(client, monkeypatch, tmp_path):
    from backend.app.core.config import get_settings

    vault = tmp_path / "cognosos-vault"
    monkeypatch.setenv("COGNOSOS_VAULT_PATH", str(vault))
    get_settings.cache_clear()

    response = client.post(
        "/flow-sessions",
        json={
            "prompt_id": "daily-review",
            "prompt_title": "Daily Review",
            "prompt_cues": ["今天值得记录的时刻"],
            "content": "Markdown vault should be the storage layer.",
            "mode": "hard",
            "status": "completed",
            "duration_seconds": 300,
            "idle_timeout_seconds": 7,
            "final_word_count": 7,
            "interruption_count": 0,
        },
    )

    assert response.status_code == 200
    note = next((vault / "Calendar").glob("*.md"))
    assert "Markdown vault should be the storage layer." in note.read_text(encoding="utf-8")


def test_failed_hard_flow_session_does_not_write_content(client, monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

    response = client.post(
        "/flow-sessions",
        json={
            "prompt_id": "daily-review",
            "prompt_title": "Daily Review",
            "prompt_cues": ["今天要感谢的三个人"],
            "content": "这段失败内容不应该写入文件",
            "mode": "hard",
            "status": "failed",
            "duration_seconds": 300,
            "idle_timeout_seconds": 7,
            "final_word_count": 12,
            "interruption_count": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["session"]["note_path"] is None
    assert not Path(vault).exists()


def test_breakthrough_flow_session_saves_stages_cards_capsules_and_projection(client, db_session, monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    stages = [
        {
            "stage_id": "mental_dump",
            "stage_order": 1,
            "module_type": "free_write",
            "title": "What is looping in your head right now?",
            "prompt_label": "PHASE 1 · THE NOISE",
            "ghost_starter": "我现在脑子里最吵的是：",
            "content": "我很焦虑，脑子里一直绕着这个 agent 项目，担心自己不知道怎么开始。",
            "word_count": 34,
            "status": "completed",
            "idle_timeout_seconds": 8,
            "metadata_json": {"extractor_hint": "noise"},
        },
        {
            "stage_id": "future_reframe",
            "stage_order": 2,
            "module_type": "future_self",
            "title": "Write from the other side of the struggle.",
            "prompt_label": "PHASE 2 · FUTURE-SELF",
            "content": "回看当时，我先把最小的数据结构稳定下来，然后才继续做界面。",
            "word_count": 30,
            "status": "completed",
            "idle_timeout_seconds": 20,
            "metadata_json": {"enforce_past_tense": True},
        },
        {
            "stage_id": "decision_snapshot",
            "stage_order": 3,
            "module_type": "decision",
            "title": "Separate your reasoning from luck.",
            "prompt_label": "PHASE 3 · DECISION SNAPSHOT",
            "content": "我决定先把 stage 作为数据库一等对象保存，预期这样后端不会再猜 Markdown。",
            "word_count": 36,
            "status": "completed",
            "idle_timeout_seconds": 30,
            "metadata_json": {"creates_time_capsule": True},
        },
        {
            "stage_id": "scaffold_action",
            "stage_order": 4,
            "module_type": "scaffolding",
            "title": "Make it startable and systematic.",
            "prompt_label": "PHASE 4 · THE SCAFFOLD",
            "content": "接下来 10 分钟先写迁移和 schema 测试，成功标准是保存后能看到四张卡。",
            "word_count": 34,
            "status": "completed",
            "idle_timeout_seconds": 30,
            "metadata_json": {"creates_time_capsule": True},
        },
        {
            "stage_id": "prediction_seal",
            "stage_order": 5,
            "module_type": "prediction",
            "title": "What do you expect reality to do now?",
            "prompt_label": "PHASE 5 · PREDICTION SEAL",
            "content": "我预测 schema 稳定后前端会更容易推进，概率 70%。检查时间：明晚。验证信号：能否连续保存五阶段内容。",
            "word_count": 46,
            "status": "completed",
            "idle_timeout_seconds": 30,
            "metadata_json": {"creates_time_capsule": True},
        },
    ]

    response = client.post(
        "/flow-sessions",
        json={
            "prompt_id": "breakthrough_canvas_v1_2",
            "prompt_title": "Breakthrough Canvas",
            "prompt_cues": ["stage-first"],
            "content": "# Breakthrough Canvas\n\nstage-aware projection",
            "compiled_markdown": "# Breakthrough Canvas\n\nstage-aware projection",
            "mode": "hard",
            "status": "completed",
            "duration_seconds": 900,
            "idle_timeout_seconds": 8,
            "final_word_count": 134,
            "interruption_count": 1,
            "structured_payload": {
                "writing_mode": "breakthrough_canvas",
                "pipeline_version": "v1.3_prediction_seal",
                "decision_stage_enabled": True,
                "stages": stages,
            },
            "pipeline_version": "v1.3_prediction_seal",
            "decision_stage_enabled": True,
            "stages": stages,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["pipeline_version"] == "v1.3_prediction_seal"
    assert payload["session"]["decision_stage_enabled"] is True
    assert payload["session"]["structured_payload"]["client_preview_markdown"] == "# Breakthrough Canvas\n\nstage-aware projection"
    assert len(payload["session"]["stages"]) == 5
    assert [card["module_type"] for card in payload["entry"]["cards"]] == [
        CardModuleType.free_write,
        CardModuleType.future_self,
        CardModuleType.decision,
        CardModuleType.scaffolding,
        CardModuleType.prediction,
    ]
    assert {capsule["action_type"] for capsule in payload["entry"]["time_capsules"]} == {
        TimeCapsuleActionType.check_decision,
        TimeCapsuleActionType.review_scaffold,
    }
    assert all("Prediction Seal" in capsule["description"] for capsule in payload["entry"]["time_capsules"])
    prediction_card = next(card for card in payload["entry"]["cards"] if card["module_type"] == CardModuleType.prediction)
    assert set(prediction_card["metadata_json"]["linked_card_ids"]) == {"decision", "scaffolding"}

    raw_entry = db_session.get(RawEntry, payload["session"]["raw_entry_id"])
    assert raw_entry is not None
    assert "stage-aware projection" not in raw_entry.content
    assert "我很焦虑" in raw_entry.content

    saved_stages = list(db_session.scalars(select(WritingSessionStage).order_by(WritingSessionStage.stage_order)))
    assert [stage.stage_id for stage in saved_stages] == [
        "mental_dump",
        "future_reframe",
        "decision_snapshot",
        "scaffold_action",
        "prediction_seal",
    ]
    assert all(stage.created_card_id for stage in saved_stages)

    note = next((vault / "Calendar").glob("*.md"))
    text = note.read_text(encoding="utf-8")
    marker = f"<!-- cognosos:flow-session:start id={payload['session']['id']} -->"
    assert marker in text
    assert "## Breakthrough Canvas" in text
    assert "### PHASE 1 · THE NOISE" in text
    append_breakthrough_canvas_to_daily_note(
        session_id=UUID(payload["session"]["id"]),
        pipeline_version=payload["session"]["pipeline_version"],
        decision_stage_enabled=payload["session"]["decision_stage_enabled"],
        stages=saved_stages,
        cards=[],
        time_capsules=[],
    )
    assert note.read_text(encoding="utf-8").count(marker) == 1
    assert "### PHASE 5 · PREDICTION SEAL" in text
    assert "### Created Objects" in text
    assert "```json" not in text


def test_breakthrough_skipped_decision_stage_does_not_create_decision_card(client, monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    stages = [
        {
            "stage_id": "mental_dump",
            "stage_order": 1,
            "module_type": "free_write",
            "prompt_label": "PHASE 1 · THE NOISE",
            "content": "我只是需要先把混乱想法倒出来。",
            "status": "completed",
        },
        {
            "stage_id": "future_reframe",
            "stage_order": 2,
            "module_type": "future_self",
            "prompt_label": "PHASE 2 · FUTURE-SELF",
            "content": "回头看，我当时只是需要睡一觉再整理。",
            "status": "completed",
        },
        {
            "stage_id": "decision_snapshot",
            "stage_order": 3,
            "module_type": "decision",
            "prompt_label": "PHASE 3 · DECISION SNAPSHOT",
            "content": "",
            "status": "skipped",
        },
        {
            "stage_id": "scaffold_action",
            "stage_order": 4,
            "module_type": "scaffolding",
            "prompt_label": "PHASE 4 · THE SCAFFOLD",
            "content": "明天早上打开项目，把今天的问题列表重新排序。",
            "status": "completed",
        },
    ]

    response = client.post(
        "/flow-sessions",
        json={
            "prompt_id": "breakthrough_canvas_v1_2",
            "prompt_title": "Breakthrough Canvas",
            "prompt_cues": [],
            "content": "# Breakthrough Canvas",
            "mode": "hard",
            "status": "completed",
            "duration_seconds": 900,
            "idle_timeout_seconds": 8,
            "final_word_count": 52,
            "interruption_count": 0,
            "pipeline_version": "v1.2_stage_first",
            "decision_stage_enabled": False,
            "stages": stages,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "decision" not in {card["module_type"] for card in payload["entry"]["cards"]}
    assert [stage["status"] for stage in payload["session"]["stages"] if stage["stage_id"] == "decision_snapshot"] == ["skipped"]
    assert {capsule["action_type"] for capsule in payload["entry"]["time_capsules"]} == {TimeCapsuleActionType.review_scaffold}


def test_prediction_ledger_creates_prediction_card_capsule_and_projection(client, monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))
    stages = [
        {
            "stage_id": "morning_forecast",
            "stage_order": 1,
            "module_type": "prediction",
            "prompt_label": "MORNING FORECAST · 5 MIN",
            "title": "Before the day unfolds, what do you expect to happen?",
            "content": "外部事件：客户会接受新时间表，概率 70%。情绪反应：下午进度慢时会焦虑。行动阻力：真正阻力是害怕对方反应。",
            "status": "completed",
            "metadata_json": {
                "creates_time_capsule": True,
                "prediction_count": 3,
                "check_at": "2026-06-22T21:00:00+00:00",
            },
        }
    ]

    response = client.post(
        "/flow-sessions",
        json={
            "prompt_id": "prediction_ledger_v1",
            "prompt_title": "Prediction Ledger",
            "prompt_cues": ["不要写目标，写可验证预测。"],
            "content": "# Prediction Ledger",
            "mode": "training",
            "status": "completed",
            "duration_seconds": 300,
            "idle_timeout_seconds": 20,
            "final_word_count": 58,
            "interruption_count": 0,
            "structured_payload": {
                "writing_mode": "prediction_ledger",
                "pipeline_version": "v1.0_prediction_ledger",
                "decision_stage_enabled": False,
                "stages": stages,
            },
            "pipeline_version": "v1.0_prediction_ledger",
            "decision_stage_enabled": False,
            "stages": stages,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert [card["module_type"] for card in payload["entry"]["cards"]] == [CardModuleType.prediction]
    assert {capsule["action_type"] for capsule in payload["entry"]["time_capsules"]} == {TimeCapsuleActionType.review_prediction}

    note = next((vault / "Calendar").glob("*.md"))
    text = note.read_text(encoding="utf-8")
    assert "## Prediction Ledger" in text
    assert "mode: prediction_ledger" in text
    assert "客户会接受新时间表" in text


def test_breakthrough_embedding_failure_preserves_local_capture(client, db_session, monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(vault))

    def fail_embed(*args, **kwargs):
        raise RuntimeError("Gemini embedding unavailable")

    monkeypatch.setattr("backend.app.services.breakthrough_canvas_service.embed_text", fail_embed)
    stages = [
        {
            "stage_id": "mental_dump",
            "stage_order": 1,
            "module_type": "free_write",
            "prompt_label": "PHASE 1 · THE NOISE",
            "content": "我今天非常焦虑，但这段内容绝对不能因为 Gemini 报错而丢掉。",
            "word_count": 28,
            "status": "completed",
            "idle_timeout_seconds": 8,
        }
    ]

    response = client.post(
        "/flow-sessions",
        json={
            "prompt_id": "breakthrough_canvas_v1_2",
            "prompt_title": "Breakthrough Canvas",
            "prompt_cues": ["stage-first"],
            "content": "# Breakthrough Canvas\n\nlocal capture should survive",
            "compiled_markdown": "# Breakthrough Canvas\n\nlocal capture should survive",
            "mode": "hard",
            "status": "completed",
            "duration_seconds": 900,
            "idle_timeout_seconds": 8,
            "final_word_count": 28,
            "interruption_count": 0,
            "pipeline_version": "v1.2_stage_first",
            "decision_stage_enabled": False,
            "stages": stages,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["session"]["raw_entry_id"]
    assert len(payload["session"]["stages"]) == 1
    assert len(payload["entry"]["cards"]) == 1

    card = payload["entry"]["cards"][0]
    assert card["embedding"] is None
    assert "embedding_error" in card["metadata_json"]

    raw_entry = db_session.get(RawEntry, payload["session"]["raw_entry_id"])
    assert raw_entry.processing_status == ProcessingStatus.processed
    assert raw_entry.error_message is not None
    assert "Partial breakthrough processing errors" in raw_entry.error_message
    assert "Gemini embedding unavailable" in raw_entry.error_message

    note = next((vault / "Calendar").glob("*.md"))
    text = note.read_text(encoding="utf-8")
    assert "## Breakthrough Canvas" in text
    assert "绝对不能因为 Gemini 报错而丢掉" in text
