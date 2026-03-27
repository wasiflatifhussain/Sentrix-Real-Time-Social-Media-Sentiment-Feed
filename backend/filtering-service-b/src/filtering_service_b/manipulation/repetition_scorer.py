from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from filtering_service_b.config.settings import ManipulationSettings
from filtering_service_b.manipulation.hamming import hamming_distance_64

REASON_CROSS_USER_REPETITION = "CROSS_USER_REPETITION"


@dataclass(frozen=True)
class CrossUserRepetitionScore:
    score_delta: float
    reason_codes: list[str]
    signals: dict[str, object]


class CrossUserRepetitionScorer:
    def __init__(self, settings: ManipulationSettings) -> None:
        self._settings = settings

    def score(
        self,
        current_simhash: int | None,
        current_author: str | None,
        ticker_similarity_history: list[dict[str, Any]] | None,
    ) -> CrossUserRepetitionScore:
        if not self._settings.cross_user_enabled:
            return CrossUserRepetitionScore(
                score_delta=0.0,
                reason_codes=[],
                signals={"stage2CrossUserEvaluated": False, "stage2CrossUserEnabled": False},
            )

        if current_simhash is None:
            return CrossUserRepetitionScore(
                score_delta=0.0,
                reason_codes=[],
                signals={"stage2CrossUserEvaluated": False, "stage2CrossUserEnabled": True},
            )

        if not current_author or not current_author.strip():
            return CrossUserRepetitionScore(
                score_delta=0.0,
                reason_codes=[],
                signals={
                    "stage2CrossUserEvaluated": False,
                    "stage2CrossUserEnabled": True,
                    "stage2CrossUserReason": "missing_author",
                },
            )

        history = ticker_similarity_history or []
        match_count = 0
        min_hamming: int | None = None
        unique_other_authors: set[str] = set()

        for row in history:
            if not isinstance(row, dict):
                continue
            other_author_raw = row.get("author")
            if not isinstance(other_author_raw, str) or not other_author_raw.strip():
                continue
            other_author = other_author_raw.strip()
            if other_author == current_author:
                continue

            candidate_hash = _parse_simhash(row.get("simHash64"))
            if candidate_hash is None:
                continue

            distance = hamming_distance_64(current_simhash, candidate_hash)
            if distance <= self._settings.cross_user_max_hamming_distance:
                match_count += 1
                unique_other_authors.add(other_author)
                min_hamming = distance if min_hamming is None else min(min_hamming, distance)

        unique_author_count = len(unique_other_authors)
        triggered = (
            match_count >= self._settings.cross_user_min_matches
            and unique_author_count >= self._settings.cross_user_min_unique_authors
        )

        penalty = 0.0
        reason_codes: list[str] = []
        if triggered:
            base_penalty = self._settings.cross_user_penalty
            if match_count >= self._settings.cross_user_strong_match_threshold:
                base_penalty = self._settings.cross_user_strong_penalty
            penalty = -abs(base_penalty)
            reason_codes = [REASON_CROSS_USER_REPETITION]

        return CrossUserRepetitionScore(
            score_delta=penalty,
            reason_codes=reason_codes,
            signals={
                "stage2CrossUserEvaluated": True,
                "stage2CrossUserEnabled": True,
                "stage2CrossUserMatchCount": match_count,
                "stage2CrossUserUniqueAuthorCount": unique_author_count,
                "stage2CrossUserMinHamming": min_hamming,
                "stage2CrossUserPenaltyApplied": float(abs(penalty)),
                "stage2CrossUserTriggered": triggered,
                "stage2CrossUserMaxHamming": self._settings.cross_user_max_hamming_distance,
            },
        )


def _parse_simhash(raw: object) -> int | None:
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
