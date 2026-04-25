from __future__ import annotations

import logging
from typing import Any

from sentiment_service.keywords.embedding_base import EmbeddingService

log = logging.getLogger(__name__)


class SentenceTransformerEmbeddingService(EmbeddingService):
    def __init__(self, model_name: str, normalize_embeddings: bool = True) -> None:
        self.model_name = model_name
        self.normalize_embeddings = normalize_embeddings
        try:
            from sentence_transformers import SentenceTransformer

            self._model = self._load_model(SentenceTransformer)
        except Exception as ex:
            raise RuntimeError(
                f"Failed to load sentence-transformer model '{model_name}'"
            ) from ex

    def _load_model(self, sentence_transformer_cls: type[Any]) -> Any:
        try:
            log.info(
                "Loading sentence-transformer model=%s from local cache first",
                self.model_name,
            )
            return sentence_transformer_cls(self.model_name, local_files_only=True)
        except Exception:
            log.info(
                "Local cache unavailable for model=%s; downloading from Hugging Face",
                self.model_name,
            )
            return sentence_transformer_cls(self.model_name)

    @property
    def model(self) -> Any:
        return self._model

    def embed_many(self, texts: list[str]) -> Any:
        if not texts:
            raise ValueError("texts must not be empty")
        try:
            import numpy as np

            vectors = self._model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=self.normalize_embeddings,
                show_progress_bar=False,
            )
        except Exception as ex:
            raise RuntimeError("Failed generating embeddings for batch") from ex
        return np.asarray(vectors, dtype=np.float32)

    def embed_one(self, text: str) -> Any:
        import numpy as np

        vectors = self.embed_many([text])
        return np.asarray(vectors[0], dtype=np.float32)
