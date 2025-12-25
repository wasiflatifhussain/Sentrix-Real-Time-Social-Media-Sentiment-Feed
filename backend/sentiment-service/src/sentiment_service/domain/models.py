from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class CleanedEvent:
    """
    Domain-level cleaned event.
    """

    event_id: str
    ticker: str
    source: str
    entity_type: str
    created_at_utc: int
    text_normalized: str


@dataclass(frozen=True)
class SentimentResult:
    """
    Domain object: output of scoring.
    """

    event_id: str
    ticker: str
    score: float  # recommend -1.0 .. +1.0
    keywords: List[str]
    confidence: Optional[float] = None  # 0.0 .. 1.0, optional
