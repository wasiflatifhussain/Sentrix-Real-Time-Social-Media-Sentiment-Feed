from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from filtering_service_b.relevance.embedding_base import EmbeddingService


class SentenceTransformerEmbeddingService(EmbeddingService):
    def __init__(self, model_name: str, normalize_embeddings: bool = True) -> None:
        self.model_name = model_name
        self._normalize_embeddings = normalize_embeddings
        try:
            self._model = SentenceTransformer(model_name)
        except Exception as ex:
            raise RuntimeError(
                f"Failed to load sentence-transformer model '{model_name}'"
            ) from ex

    def embed_many(self, texts: list[str]) -> np.ndarray:
        if not texts:
            raise ValueError("texts must not be empty")
        try:
            vectors = self._model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=self._normalize_embeddings,
                show_progress_bar=False,
            )
        except Exception as ex:
            raise RuntimeError("Failed generating embeddings for batch") from ex
        return np.asarray(vectors, dtype=np.float32)

    def embed_one(self, text: str) -> np.ndarray:
        vectors = self.embed_many([text])
        return np.asarray(vectors[0], dtype=np.float32)
