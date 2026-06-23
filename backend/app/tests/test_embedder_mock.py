from backend.app.providers.embedder_mock import MockEmbedder


def test_mock_embedder_dimension_and_determinism():
    embedder = MockEmbedder(dimension=1024)

    first = embedder.embed("agent 系统太复杂")
    second = embedder.embed("agent 系统太复杂")

    assert len(first) == 1024
    assert first == second

