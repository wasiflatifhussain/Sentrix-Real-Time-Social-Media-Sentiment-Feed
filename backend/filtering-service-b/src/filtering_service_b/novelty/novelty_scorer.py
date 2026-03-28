from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from filtering_service_b.config.settings import NoveltySettings
from filtering_service_b.relevance.embedding_base import EmbeddingService

REASON_LOW_NOVELTY = "LOW_NOVELTY"


@dataclass(frozen=True)
class NoveltyScore:
    score_delta: float
    reason_codes: list[str]
    signals: dict[str, object]


class NoveltyScorer:
    def __init__(self, embedding_service: EmbeddingService, settings: NoveltySettings) -> None:
        self._embedding_service = embedding_service
        self._settings = settings

    def score(
        self,
        event_text: str,
        accepted_references: list[dict[str, Any]] | None,
    ) -> NoveltyScore:
        if not self._settings.enabled:
            return NoveltyScore(
                score_delta=0.0,
                reason_codes=[],
                signals={"stage3NoveltyEvaluated": False, "stage3NoveltyEnabled": False},
            )

        refs = _extract_reference_texts(
            accepted_references=accepted_references,
            max_references=self._settings.max_references,
        )
        if not refs:
            return NoveltyScore(
                score_delta=0.0,
                reason_codes=[],
                signals={
                    "stage3NoveltyEvaluated": True,
                    "stage3NoveltyEnabled": True,
                    "stage3NoveltyReferenceCount": 0,
                    "stage3NoveltyReason": "no_references",
                    "stage3NoveltyMaxSimilarity": None,
                    "stage3NoveltyBand": "insufficient_reference",
                    "stage3NoveltyPenaltyApplied": 0.0,
                    "stage3NoveltyBoostApplied": 0.0,
                },
            )

        embedding_texts = [event_text, *refs]
        vectors = np.asarray(
            self._embedding_service.embed_many(embedding_texts), dtype=np.float32
        )
        current_vector = vectors[0]
        reference_vectors = vectors[1:]
        max_similarity = _max_cosine_similarity(current_vector, reference_vectors)

        score_delta = 0.0
        reason_codes: list[str] = []
        novelty_band = "moderate_novelty"
        penalty_applied = 0.0
        boost_applied = 0.0

        if max_similarity >= self._settings.low_similarity_threshold:
            penalty_applied = abs(self._settings.low_penalty)
            score_delta = -penalty_applied
            reason_codes = [REASON_LOW_NOVELTY]
            novelty_band = "low_novelty"
        elif max_similarity >= self._settings.medium_similarity_threshold:
            penalty_applied = abs(self._settings.medium_penalty)
            score_delta = -penalty_applied
            novelty_band = "moderate_low_novelty"
        elif (
            len(refs) >= self._settings.min_references_for_distinct_boost
            and max_similarity <= self._settings.distinct_similarity_threshold
        ):
            boost_applied = abs(self._settings.distinct_boost)
            score_delta = boost_applied
            novelty_band = "high_novelty"

        return NoveltyScore(
            score_delta=score_delta,
            reason_codes=reason_codes,
            signals={
                "stage3NoveltyEvaluated": True,
                "stage3NoveltyEnabled": True,
                "stage3NoveltyReferenceCount": len(refs),
                "stage3NoveltyMaxSimilarity": float(max_similarity),
                "stage3NoveltyBand": novelty_band,
                "stage3NoveltyPenaltyApplied": float(penalty_applied),
                "stage3NoveltyBoostApplied": float(boost_applied),
                "stage3NoveltyMediumThreshold": self._settings.medium_similarity_threshold,
                "stage3NoveltyLowThreshold": self._settings.low_similarity_threshold,
                "stage3NoveltyDistinctThreshold": self._settings.distinct_similarity_threshold,
            },
        )


def _extract_reference_texts(
    accepted_references: list[dict[str, Any]] | None,
    max_references: int,
) -> list[str]:
    rows = accepted_references or []
    out: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text_value = row.get("text")
        title_value = row.get("title")
        text = str(text_value).strip() if isinstance(text_value, str) else ""
        title = str(title_value).strip() if isinstance(title_value, str) else ""
        if not text and not title:
            continue
        if title and text and text.lower().startswith(title.lower()):
            combined = text
        elif title and text:
            combined = f"{title} {text}"
        else:
            combined = title or text
        out.append(combined)
        if len(out) >= max_references:
            break
    return out


def _max_cosine_similarity(current: np.ndarray, refs: np.ndarray) -> float:
    if refs.size == 0:
        return 0.0

    current = np.asarray(current, dtype=np.float32).reshape(-1)
    refs = np.asarray(refs, dtype=np.float32)
    if refs.ndim == 1:
        refs = refs.reshape(1, -1)

    current_norm = np.linalg.norm(current)
    ref_norms = np.linalg.norm(refs, axis=1)
    denoms = ref_norms * current_norm
    safe_denoms = np.where(denoms > 0.0, denoms, 1.0)
    similarities = (refs @ current) / safe_denoms
    similarities = np.where(denoms > 0.0, similarities, 0.0)
    return float(np.max(similarities))
