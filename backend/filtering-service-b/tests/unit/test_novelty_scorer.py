import math

import numpy as np

from filtering_service_b.config.settings import NoveltySettings
from filtering_service_b.novelty.novelty_scorer import (
    REASON_LOW_NOVELTY,
    NoveltyScorer,
)


class FakeEmbeddingService:
    def __init__(self, vectors_by_text: dict[str, list[float]]) -> None:
        self._vectors = {
            key: np.asarray(value, dtype=np.float32)
            for key, value in vectors_by_text.items()
        }

    def embed_many(self, texts: list[str]) -> np.ndarray:
        return np.asarray([self._vectors[t] for t in texts], dtype=np.float32)

    def embed_one(self, text: str) -> np.ndarray:
        return np.asarray(self._vectors[text], dtype=np.float32)


def _settings() -> NoveltySettings:
    return NoveltySettings(
        enabled=True,
        max_references=20,
        medium_similarity_threshold=0.82,
        low_similarity_threshold=0.92,
        medium_penalty=0.10,
        low_penalty=0.20,
        distinct_similarity_threshold=0.45,
        distinct_boost=0.03,
        min_references_for_distinct_boost=3,
    )


def _vec(similarity: float) -> list[float]:
    return [similarity, math.sqrt(1.0 - similarity * similarity)]


def test_novelty_no_reference_is_neutral() -> None:
    scorer = NoveltyScorer(
        embedding_service=FakeEmbeddingService({"event": [1.0, 0.0]}),
        settings=_settings(),
    )
    result = scorer.score(event_text="event", accepted_references=[])
    assert result.score_delta == 0.0
    assert result.reason_codes == []
    assert result.signals["stage3NoveltyReason"] == "no_references"


def test_novelty_low_similarity_penalty_with_reason() -> None:
    scorer = NoveltyScorer(
        embedding_service=FakeEmbeddingService(
            {
                "event": [1.0, 0.0],
                "ref_a": _vec(0.94),
                "ref_b": _vec(0.88),
            }
        ),
        settings=_settings(),
    )
    result = scorer.score(
        event_text="event",
        accepted_references=[{"text": "ref_a"}, {"text": "ref_b"}],
    )
    assert math.isclose(result.score_delta, -0.20, abs_tol=1e-9)
    assert result.reason_codes == [REASON_LOW_NOVELTY]
    assert result.signals["stage3NoveltyBand"] == "low_novelty"


def test_novelty_medium_similarity_penalty_without_reason_code() -> None:
    scorer = NoveltyScorer(
        embedding_service=FakeEmbeddingService(
            {
                "event": [1.0, 0.0],
                "ref_a": _vec(0.86),
            }
        ),
        settings=_settings(),
    )
    result = scorer.score(
        event_text="event",
        accepted_references=[{"text": "ref_a"}],
    )
    assert math.isclose(result.score_delta, -0.10, abs_tol=1e-9)
    assert result.reason_codes == []
    assert result.signals["stage3NoveltyBand"] == "moderate_low_novelty"


def test_novelty_distinct_boost_when_far_from_references() -> None:
    scorer = NoveltyScorer(
        embedding_service=FakeEmbeddingService(
            {
                "event": [1.0, 0.0],
                "ref_a": _vec(0.20),
                "ref_b": _vec(0.30),
                "ref_c": _vec(0.40),
            }
        ),
        settings=_settings(),
    )
    result = scorer.score(
        event_text="event",
        accepted_references=[{"text": "ref_a"}, {"text": "ref_b"}, {"text": "ref_c"}],
    )
    assert math.isclose(result.score_delta, 0.03, abs_tol=1e-9)
    assert result.reason_codes == []
    assert result.signals["stage3NoveltyBand"] == "high_novelty"
