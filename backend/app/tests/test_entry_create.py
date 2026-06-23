def test_post_entries_stores_raw_entry(client):
    create_response = client.post(
        "/entries",
        json={"content": "今天有点焦虑，agent 系统太复杂了。", "source": "text"},
    )

    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["entry_id"]
    assert len(payload["cards"]) == 1
    assert payload["cards"][0]["module_type"] == "free_write"
    assert payload["trigger_events"] == []
    assert payload["time_capsules"] == []

    read_response = client.get(f"/entries/{payload['entry_id']}")
    assert read_response.status_code == 200
    entry = read_response.json()
    assert entry["content"] == "今天有点焦虑，agent 系统太复杂了。"
    assert entry["source"] == "text"
    assert entry["processing_status"] == "processed"


def test_post_entries_does_not_leak_internal_errors(client, monkeypatch):
    def fail_process_entry(*_args, **_kwargs):
        raise RuntimeError("database failed with internal_error_marker")

    monkeypatch.setattr("backend.app.api.routes_entries.process_entry", fail_process_entry)

    response = client.post("/entries", json={"content": "private text", "source": "text"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to process entry"


def test_get_cards_returns_empty_list_initially(client):
    response = client.get("/cards")

    assert response.status_code == 200
    assert response.json() == []


def test_get_time_capsules_returns_empty_list_initially(client):
    response = client.get("/time-capsules")

    assert response.status_code == 200
    assert response.json() == []
