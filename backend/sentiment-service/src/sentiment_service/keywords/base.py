from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class KeywordCandidate:
    phrase: str
    score: float


class KeywordExtractor(Protocol):
    def extract_candidates(
        self,
        text: str,
        *,
        ticker: str | None = None,
        source: str | None = None,
    ) -> list[KeywordCandidate]: ...

    def extract(
        self,
        text: str,
        *,
        ticker: str | None = None,
        source: str | None = None,
    ) -> list[str]: ...
