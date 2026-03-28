from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List

from sentiment_service.domain.models import SentimentResult
from sentiment_service.messaging.schemas import CleanedEvent

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
        StubSentimentScorer.calculate_components(event)  # -1..+1
        keywords = self._extract_keywords(
            event.text_normalized or "", self.max_keywords
        )

        return SentimentResult(
            event_id=event.event_id,
            ticker=event.ticker,
            score=event.absolute_score,
            keywords=keywords,
            confidence=event.conf,
        )
    
    @staticmethod
    def clamp(x: float, low: float, high:float) -> float:
        return max(low, min(high, x))

    @staticmethod
    def _arrange_response(event: CleanedEvent) -> None:
        tmp = {}
        if event.response is not None:
            for re in event.response:
                tmp[re["label"]] = re["score"]

        event.response = tmp
        return

    @staticmethod
    def calculate_score(p_pos, p_neg) -> float:
        return StubSentimentScorer.clamp(p_pos - p_neg, -1.0, 1.0)
    
    @staticmethod
    def calculate_conf(p_pos, p_neg, p_neu) -> float:
        sorted_probs = sorted([p_pos, p_neu, p_neg], reverse=True)
        return StubSentimentScorer.clamp(sorted_probs[0] - sorted_probs[1], 0.0, 1.0)

    @staticmethod
    def set_label(p_pos, p_neg, p_neu) -> str:
        if p_pos >= p_neu and p_pos >= p_neg:
            return "positive"
        elif p_neg >= p_neu and p_neg >= p_pos:
            return "negative"
        return "neutral"

    
    @staticmethod
    def calculate_data(event: CleanedEvent) -> None:
        p_pos: float = float(event.response.get("positive", 0.0))
        p_neg: float = float(event.response.get("neutral", 0.0))
        p_neu: float = float(event.response.get("negative", 0.0))

        event.absolute_score = StubSentimentScorer.calculate_score(p_pos, p_neg)
        event.conf = StubSentimentScorer.calculate_conf(p_pos, p_neg, p_neu)
        event.label = StubSentimentScorer.set_label(p_pos, p_neg, p_neu)
        return

    @staticmethod
    def calculate_components(event: CleanedEvent) -> None:
        StubSentimentScorer._arrange_response(event)
        StubSentimentScorer.calculate_data(event)
        return

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
