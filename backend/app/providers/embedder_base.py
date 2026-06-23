from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal

EmbeddingInputType = Literal["document", "query", "similarity"]


class Embedder(ABC):
    model_name: str
    dimension: int

    @abstractmethod
    def embed(self, text: str, input_type: EmbeddingInputType = "document") -> list[float]:
        raise NotImplementedError
