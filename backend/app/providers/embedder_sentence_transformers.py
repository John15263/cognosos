from __future__ import annotations

from backend.app.providers.embedder_base import Embedder, EmbeddingInputType


class SentenceTransformersEmbedder(Embedder):
    def __init__(self, model_name: str, dimension: int, normalize: bool = True) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. Install with "
                "`pip install -e '.[embeddings]'` or use EMBEDDING_PROVIDER=mock."
            ) from exc

        self.model_name = model_name
        self.dimension = dimension
        self.normalize = normalize
        self._model = SentenceTransformer(model_name)

    def embed(self, text: str, input_type: EmbeddingInputType = "document") -> list[float]:
        vector = self._model.encode(text, normalize_embeddings=self.normalize)
        values = vector.tolist()
        if len(values) != self.dimension:
            raise ValueError(f"Embedding dimension mismatch: got {len(values)}, expected {self.dimension}")
        return [float(value) for value in values]
