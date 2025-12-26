from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List

from sentiment_service.domain.models import CleanedEvent, SentimentResult

_WORD_RE = re.compile(r"[A-Za-z]{3,}")  # simple tokenization (>=3 letters)


@dataclass(frozen=True)
class StubSentimentScorer:
    """
    Stub sentiment scorer for development / testing.
    - Deterministic (based on event_id)
    - No ML deps
    - Intended to be replaced later with FinBERT/HF/etc while keeping the same .score(event) contract
    """

    max_keywords: int = 10

    def score(self, event: CleanedEvent) -> SentimentResult:
        score = self._deterministic_score(event.event_id)  # -1..+1
        keywords = self._extract_keywords(
            event.text_normalized or "", self.max_keywords
        )
        confidence = self._deterministic_confidence(event.event_id)  # 0..1 (optional)

        return SentimentResult(
            event_id=event.event_id,
            ticker=event.ticker,
            score=score,
            keywords=keywords,
            confidence=confidence,
        )

    @staticmethod
    def _deterministic_score(event_id: str) -> float:
        """
        Stable pseudo-score in [-1, 1], derived from event_id hash.
        """
        h = hashlib.sha256(event_id.encode("utf-8")).digest()
        n = int.from_bytes(h[:8], "big")  # 64-bit
        x = (n % 20001) / 10000.0  # 0..2.0000
        return x - 1.0  # -1..+1

    @staticmethod
    def _deterministic_confidence(event_id: str) -> float:
        """
        Stable pseudo-confidence in [0, 1], derived from event_id hash.
        """
        h = hashlib.sha256((event_id + "|conf").encode("utf-8")).digest()
        n = int.from_bytes(h[:8], "big")
        return (n % 10001) / 10000.0  # 0..1

    @staticmethod
    def _extract_keywords(text: str, k: int) -> List[str]:
        """
        Simple keyword extractor:
        - tokenize words
        - lowercase
        - count frequency
        - return top-k

        Intended to be replaced later with TF-IDF / KeyBERT etc without changing SentimentResult.
        """
        tokens = [t.lower() for t in _WORD_RE.findall(text)]
        if not tokens:
            return []

        freq = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1

        ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
        return [w for (w, _) in ranked[:k]]
