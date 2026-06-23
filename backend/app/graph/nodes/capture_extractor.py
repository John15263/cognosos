from backend.app.services.llm_service import get_llm_provider


def capture_extractor(raw_input: str):
    return get_llm_provider().extract_cards(raw_input)

