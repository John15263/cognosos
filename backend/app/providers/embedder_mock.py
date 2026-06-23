from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterable

from backend.app.providers.embedder_base import Embedder, EmbeddingInputType


TOKEN_RE = re.compile(r"[A-Za-z0-9_+#.-]+|[\u4e00-\u9fff]")


class MockEmbedder(Embedder):
    model_name = "mock-hashed-bow"

    def __init__(self, dimension: int = 1024) -> None:
        self.dimension = dimension

    def embed(self, text: str, input_type: EmbeddingInputType = "document") -> list[float]:
        vector = [0.0] * self.dimension
        for token in self._tokens(text):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]

    def _tokens(self, text: str) -> Iterable[str]:
        lowered = text.lower()
        yield from TOKEN_RE.findall(lowered)

        # Add lightweight phrase features for Chinese text where word boundaries are absent.
        compact = re.sub(r"\s+", "", lowered)
        for size in (2, 3):
            for index in range(max(0, len(compact) - size + 1)):
                token = compact[index : index + size]
                if any("\u4e00" <= char <= "\u9fff" for char in token):
                    yield token
