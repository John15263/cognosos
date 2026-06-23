from __future__ import annotations

from functools import lru_cache

from backend.app.core.config import get_settings
from backend.app.providers.embedder_base import Embedder
from backend.app.providers.embedder_gemini import GeminiEmbedder
from backend.app.providers.embedder_mock import MockEmbedder
from backend.app.providers.embedder_sentence_transformers import SentenceTransformersEmbedder


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embedding_provider == "mock":
        return MockEmbedder(settings.embedding_dim)

    if settings.embedding_provider == "gemini":
        if not settings.allow_remote_llm:
            raise RuntimeError("Gemini embeddings are remote calls. Set ALLOW_REMOTE_LLM=true to enable them.")
        model_name = settings.embedding_model
        if model_name == "BAAI/bge-m3":
            model_name = "gemini-embedding-2"
        return GeminiEmbedder(
            api_key=settings.gemini_api_key or "",
            model_name=model_name,
            dimension=settings.embedding_dim,
        )

    if settings.embedding_provider == "sentence_transformers":
        try:
            return SentenceTransformersEmbedder(
                model_name=settings.embedding_model,
                dimension=settings.embedding_dim,
                normalize=settings.embedding_normalize,
            )
        except RuntimeError:
            # Keep the prototype runnable without downloading a large model.
            return MockEmbedder(settings.embedding_dim)

    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")


def embed_text(text: str, input_type: str = "document") -> tuple[list[float], str, int]:
    embedder = get_embedder()
    vector = embedder.embed(text, input_type=input_type)  # type: ignore[arg-type]
    if len(vector) != embedder.dimension:
        raise ValueError(f"Embedding dimension mismatch: got {len(vector)}, expected {embedder.dimension}")
    return vector, embedder.model_name, embedder.dimension
