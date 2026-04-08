from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class EmbeddingService(ABC):
    @abstractmethod
    def embed_many(self, texts: list[str]) -> Any:
        raise NotImplementedError

    @abstractmethod
    def embed_one(self, text: str) -> Any:
        raise NotImplementedError
