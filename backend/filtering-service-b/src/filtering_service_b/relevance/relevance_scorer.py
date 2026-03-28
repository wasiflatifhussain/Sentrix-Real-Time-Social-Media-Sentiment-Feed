from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from filtering_service_b.config.settings import RelevanceSettings
from filtering_service_b.relevance.embedding_base import EmbeddingService
from filtering_service_b.relevance.ticker_profiles import TickerProfileStore

DECISION_KEEP = "KEEP"
DECISION_REJECT = "REJECT"
REASON_UNKNOWN_TICKER_PROFILE = "UNKNOWN_TICKER_PROFILE"
REASON_LOW_TICKER_RELEVANCE = "LOW_TICKER_RELEVANCE"
REASON_EXTREME_LOW_TICKER_RELEVANCE = "EXTREME_LOW_TICKER_RELEVANCE"


@dataclass(frozen=True)
class RelevanceScore:
    decision: str
    score_delta: float
    similarity: float | None
    reason_codes: list[str]
    signals: dict[str, object]


class TickerRelevanceScorer:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        ticker_profiles: TickerProfileStore,
        settings: RelevanceSettings,
    ) -> None:
        self._embedding_service = embedding_service
        self._ticker_profiles = ticker_profiles
        self._settings = settings
        self._profile_embeddings = self._build_profile_embeddings()

    def score(self, event_text: str, ticker: str) -> RelevanceScore:
        normalized_ticker = ticker.upper()
        profile_vector = self._profile_embeddings.get(normalized_ticker)
        if profile_vector is None:
            if self._settings.reject_unknown_ticker_profile:
                return RelevanceScore(
                    decision=DECISION_REJECT,
                    score_delta=-1.0,
                    similarity=None,
                    reason_codes=[REASON_UNKNOWN_TICKER_PROFILE],
                    signals=self._build_signals(
                        similarity=None,
                        band="unknown_ticker_profile",
                        ticker_profile_found=False,
                        score_delta=-1.0,
                    ),
                )
            return RelevanceScore(
                decision=DECISION_KEEP,
                score_delta=0.0,
                similarity=None,
                reason_codes=[],
                signals=self._build_signals(
                    similarity=None,
                    band="unknown_ticker_profile",
                    ticker_profile_found=False,
                    score_delta=0.0,
                ),
            )

        event_vector = np.asarray(
            self._embedding_service.embed_one(event_text), dtype=np.float32
        )
        similarity = _cosine_similarity(event_vector, profile_vector)

        if similarity < self._settings.low_similarity_threshold:
            return RelevanceScore(
                decision=DECISION_REJECT,
                score_delta=-1.0,
                similarity=similarity,
                reason_codes=[REASON_EXTREME_LOW_TICKER_RELEVANCE],
                signals=self._build_signals(
                    similarity=similarity,
                    band="extreme_low_relevance",
                    ticker_profile_found=True,
                    score_delta=-1.0,
                ),
            )

        if similarity < self._settings.medium_similarity_threshold:
            return RelevanceScore(
                decision=DECISION_KEEP,
                score_delta=-abs(self._settings.low_relevance_penalty),
                similarity=similarity,
                reason_codes=[REASON_LOW_TICKER_RELEVANCE],
                signals=self._build_signals(
                    similarity=similarity,
                    band="low_relevance",
                    ticker_profile_found=True,
                    score_delta=-abs(self._settings.low_relevance_penalty),
                ),
            )

        if similarity < self._settings.strong_similarity_threshold:
            return RelevanceScore(
                decision=DECISION_KEEP,
                score_delta=-abs(self._settings.medium_relevance_penalty),
                similarity=similarity,
                reason_codes=[],
                signals=self._build_signals(
                    similarity=similarity,
                    band="moderate_relevance",
                    ticker_profile_found=True,
                    score_delta=-abs(self._settings.medium_relevance_penalty),
                ),
            )

        return RelevanceScore(
            decision=DECISION_KEEP,
            score_delta=abs(self._settings.strong_relevance_boost),
            similarity=similarity,
            reason_codes=[],
            signals=self._build_signals(
                similarity=similarity,
                band="strong_relevance",
                ticker_profile_found=True,
                score_delta=abs(self._settings.strong_relevance_boost),
            ),
        )

    def _build_profile_embeddings(self) -> dict[str, np.ndarray]:
        if not self._ticker_profiles.profiles:
            return {}
        tickers = list(self._ticker_profiles.profiles.keys())
        profile_texts = [
            self._ticker_profiles.profiles[t].profile_text for t in tickers
        ]
        vectors = np.asarray(
            self._embedding_service.embed_many(profile_texts), dtype=np.float32
        )
        if vectors.shape[0] != len(tickers):
            raise ValueError(
                "Embedding service returned unexpected number of vectors "
                f"(expected={len(tickers)}, got={vectors.shape[0]})"
            )
        return {ticker: vectors[idx] for idx, ticker in enumerate(tickers)}

    def _build_signals(
        self,
        similarity: float | None,
        band: str,
        ticker_profile_found: bool,
        score_delta: float,
    ) -> dict[str, object]:
        return {
            "relevanceSimilarity": similarity,
            "relevanceBand": band,
            "tickerProfileFound": ticker_profile_found,
            "relevanceModel": self._settings.model_name,
            "relevanceScoreDelta": float(score_delta),
        }


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float32).reshape(-1)
    b = np.asarray(b, dtype=np.float32).reshape(-1)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom <= 0.0:
        return 0.0
    return float(np.dot(a, b) / denom)
