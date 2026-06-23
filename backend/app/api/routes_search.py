from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.schemas import SearchRequest, SearchResponse
from backend.app.services.embedding_service import embed_text
from backend.app.services.retrieval_service import retrieve_similar_cards

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
def search_cards(payload: SearchRequest, db: Session = Depends(get_db)) -> SearchResponse:
    vector, _model_name, _dimension = embed_text(payload.query, input_type="query")
    results = retrieve_similar_cards(
        db,
        query_embedding=vector,
        module_types=payload.module_types,
        statuses=payload.statuses,
        days_back=payload.days_back,
        limit=payload.limit,
        min_similarity=payload.min_similarity,
    )
    return SearchResponse(results=results)
