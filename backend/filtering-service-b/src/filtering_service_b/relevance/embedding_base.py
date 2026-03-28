from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class EmbeddingService(ABC):
    @abstractmethod
    def embed_many(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError

    @abstractmethod
    def embed_one(self, text: str) -> np.ndarray:
        raise NotImplementedError
