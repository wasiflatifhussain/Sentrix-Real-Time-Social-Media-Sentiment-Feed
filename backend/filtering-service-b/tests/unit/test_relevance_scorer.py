import math

import numpy as np
from filtering_service_b.config.settings import RelevanceSettings
from filtering_service_b.relevance.relevance_scorer import TickerRelevanceScorer
from filtering_service_b.relevance.ticker_profiles import (
    TickerProfile,
    TickerProfileStore,
)


class FakeEmbeddingService:
    def __init__(self, vectors_by_text: dict[str, list[float]]) -> None:
        self._vectors = {
            k: np.asarray(v, dtype=np.float32) for k, v in vectors_by_text.items()
        }

    def embed_many(self, texts: list[str]) -> np.ndarray:
        return np.asarray([self._vectors[t] for t in texts], dtype=np.float32)

    def embed_one(self, text: str) -> np.ndarray:
        return np.asarray(self._vectors[text], dtype=np.float32)


def _settings() -> RelevanceSettings:
    return RelevanceSettings(
        model_name="test-mini-model",
        ticker_profiles_path="/tmp/tickers.json",
        strong_similarity_threshold=0.58,
        medium_similarity_threshold=0.45,
        low_similarity_threshold=0.30,
        strong_relevance_boost=0.02,
        medium_relevance_penalty=0.15,
        low_relevance_penalty=0.40,
        hard_reject_extreme_low=True,
        extreme_low_relevance_penalty=0.70,
        reject_unknown_ticker_profile=True,
        normalize_embeddings=True,
    )


def _make_vector(similarity: float) -> list[float]:
    return [similarity, math.sqrt(1.0 - (similarity * similarity))]


def test_relevance_bands_and_reason_codes() -> None:
    ticker_profile = TickerProfile(
        ticker="TSLA", company="Tesla", profile_text="profile_tsla"
    )
    profiles = TickerProfileStore({"TSLA": ticker_profile})
    embeddings = FakeEmbeddingService(
        vectors_by_text={
            "profile_tsla": [1.0, 0.0],
            "high": _make_vector(0.90),
            "moderate": _make_vector(0.50),
            "low": _make_vector(0.35),
            "extreme": _make_vector(0.10),
        }
    )
    scorer = TickerRelevanceScorer(
        embedding_service=embeddings, ticker_profiles=profiles, settings=_settings()
    )

    high = scorer.score(event_text="high", ticker="TSLA")
    moderate = scorer.score(event_text="moderate", ticker="TSLA")
    low = scorer.score(event_text="low", ticker="TSLA")
    extreme = scorer.score(event_text="extreme", ticker="TSLA")

    assert high.decision == "KEEP"
    assert high.score_delta == 0.02
    assert high.reason_codes == []
    assert high.signals["relevanceBand"] == "strong_relevance"

    assert moderate.decision == "KEEP"
    assert moderate.score_delta == -0.15
    assert moderate.reason_codes == []
    assert moderate.signals["relevanceBand"] == "moderate_relevance"

    assert low.decision == "KEEP"
    assert low.score_delta == -0.40
    assert low.reason_codes == ["LOW_TICKER_RELEVANCE"]
    assert low.signals["relevanceBand"] == "low_relevance"

    assert extreme.decision == "REJECT"
    assert extreme.score_delta == -1.0
    assert extreme.reason_codes == ["EXTREME_LOW_TICKER_RELEVANCE"]
    assert extreme.signals["relevanceBand"] == "extreme_low_relevance"


def test_extreme_low_can_be_soft_penalty_without_hard_reject() -> None:
    ticker_profile = TickerProfile(
        ticker="TSLA", company="Tesla", profile_text="profile_tsla"
    )
    profiles = TickerProfileStore({"TSLA": ticker_profile})
    embeddings = FakeEmbeddingService(
        vectors_by_text={
            "profile_tsla": [1.0, 0.0],
            "extreme": _make_vector(0.10),
        }
    )
    settings = _settings()
    settings = RelevanceSettings(
        model_name=settings.model_name,
        ticker_profiles_path=settings.ticker_profiles_path,
        strong_similarity_threshold=settings.strong_similarity_threshold,
        medium_similarity_threshold=settings.medium_similarity_threshold,
        low_similarity_threshold=settings.low_similarity_threshold,
        strong_relevance_boost=settings.strong_relevance_boost,
        medium_relevance_penalty=settings.medium_relevance_penalty,
        low_relevance_penalty=settings.low_relevance_penalty,
        hard_reject_extreme_low=False,
        extreme_low_relevance_penalty=0.70,
        reject_unknown_ticker_profile=settings.reject_unknown_ticker_profile,
        normalize_embeddings=settings.normalize_embeddings,
    )
    scorer = TickerRelevanceScorer(
        embedding_service=embeddings, ticker_profiles=profiles, settings=settings
    )

    extreme = scorer.score(event_text="extreme", ticker="TSLA")

    assert extreme.decision == "KEEP"
    assert extreme.score_delta == -0.70
    assert extreme.reason_codes == ["EXTREME_LOW_TICKER_RELEVANCE"]
    assert extreme.signals["relevanceBand"] == "extreme_low_relevance_soft"


def test_unknown_ticker_profile_rejected() -> None:
    profiles = TickerProfileStore({})
    embeddings = FakeEmbeddingService(vectors_by_text={})
    scorer = TickerRelevanceScorer(
        embedding_service=embeddings, ticker_profiles=profiles, settings=_settings()
    )

    result = scorer.score(event_text="anything", ticker="UNKNOWN")

    assert result.decision == "REJECT"
    assert result.reason_codes == ["UNKNOWN_TICKER_PROFILE"]
    assert result.similarity is None
    assert result.signals["tickerProfileFound"] is False
