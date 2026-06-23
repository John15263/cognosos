from backend.app.providers.llm_mock import MockLLMProvider


def test_mock_extractor_splits_mixed_entry():
    output = MockLLMProvider().extract_cards(
        "今天很焦虑，agent 系统太复杂了。我决定明天先做最小 demo。另外我想理解 pgvector。"
    )

    module_types = [card.module_type.value for card in output.cards]

    assert "free_write" in module_types
    assert "decision" in module_types
    assert "avsi" in module_types

