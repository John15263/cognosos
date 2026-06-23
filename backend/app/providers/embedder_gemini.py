from __future__ import annotations

import math
from typing import Any

from backend.app.providers.embedder_base import Embedder, EmbeddingInputType


class GeminiEmbedder(Embedder):
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-embedding-2",
        dimension: int = 1024,
        client: Any | None = None,
    ) -> None:
        if not api_key and client is None:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini embeddings.")

        self.model_name = model_name
        self.dimension = dimension
        self._types = None
        if client is not None:
            self._client = client
            return

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("google-genai is not installed. Install with `pip install -e '.[gemini]'`.") from exc

        self._types = types
        self._client = genai.Client(api_key=api_key)

    def embed(self, text: str, input_type: EmbeddingInputType = "document") -> list[float]:
        content = self._prepare_content(text, input_type)
        config = self._embedding_config(input_type)
        result = self._client.models.embed_content(
            model=self.model_name,
            contents=content,
            config=config,
        )
        values = self._extract_values(result)
        if len(values) != self.dimension:
            raise ValueError(f"Gemini embedding dimension mismatch: got {len(values)}, expected {self.dimension}")
        return values

    def _prepare_content(self, text: str, input_type: EmbeddingInputType) -> str:
        if self.model_name == "gemini-embedding-2":
            if input_type == "query":
                return f"task: search result | query: {text}"
            if input_type == "document":
                return f"title: none | text: {text}"
            return f"task: sentence similarity | query: {text}"
        return text

    def _embedding_config(self, input_type: EmbeddingInputType) -> Any:
        task_type = self._task_type(input_type)
        if self._types is not None:
            kwargs: dict[str, Any] = {"output_dimensionality": self.dimension}
            if task_type is not None:
                kwargs["task_type"] = task_type
            return self._types.EmbedContentConfig(**kwargs)

        config: dict[str, Any] = {"output_dimensionality": self.dimension}
        if task_type is not None:
            config["task_type"] = task_type
        return config

    def _task_type(self, input_type: EmbeddingInputType) -> str | None:
        if self.model_name == "gemini-embedding-2":
            return None
        if input_type == "query":
            return "RETRIEVAL_QUERY"
        if input_type == "document":
            return "RETRIEVAL_DOCUMENT"
        return "SEMANTIC_SIMILARITY"

    def _extract_values(self, result: Any) -> list[float]:
        embeddings = getattr(result, "embeddings", None)
        if embeddings is None and isinstance(result, dict):
            embeddings = result.get("embeddings")
        if not embeddings:
            raise ValueError("Gemini returned no embeddings.")

        first = embeddings[0]
        values = getattr(first, "values", None)
        if values is None and isinstance(first, dict):
            values = first.get("values")
        if values is None:
            raise ValueError("Gemini embedding response did not include values.")

        output = [float(value) for value in values]
        if self.model_name != "gemini-embedding-2":
            output = self._normalize(output)
        return output

    def _normalize(self, values: list[float]) -> list[float]:
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0:
            return values
        return [value / norm for value in values]

