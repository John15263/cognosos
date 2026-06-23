from backend.app.services.llm_service import get_llm_provider


def ai_judge_router(candidates):
    return get_llm_provider().judge_triggers(candidates)

