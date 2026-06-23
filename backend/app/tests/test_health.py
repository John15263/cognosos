def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_shutdown_requires_header(client):
    response = client.post("/shutdown", json={})

    assert response.status_code == 403


def test_shutdown_accepts_local_header(client, monkeypatch):
    monkeypatch.setattr("backend.app.api.routes_health._shutdown_local_app", lambda: None)

    response = client.post("/shutdown", json={}, headers={"X-CognosOS-Shutdown": "1"})

    assert response.status_code == 200
    assert response.json() == {"status": "stopping"}
