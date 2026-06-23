def test_search_returns_similar_cards(client):
    client.post("/entries", json={"content": "今天很焦虑，agent 系统太复杂了。", "source": "text"})

    response = client.post(
        "/search",
        json={
            "query": "agent 系统太复杂",
            "statuses": ["open"],
            "days_back": 90,
            "limit": 5,
            "min_similarity": 0.1,
        },
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) >= 1
    assert results[0]["module_type"] == "free_write"

