from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional

from sentiment_service.domain.models import SentimentResult


@dataclass(frozen=True)
class HourlyAggregate:
    """
    In-memory representation of an hourly bucket summary.
    This maps to Mongo docs - stored as one doc per (ticker, hour) pair in MongoDB collection.

    Notes:
    - store score_sum + count for stable incremental updates
    - avg_score is derived (property) to avoid rounding drift
    - keywords are maintained as bounded counts then projected to a top list
    """

    ticker: str
    hour_start_utc: int
    hour_end_utc: int

    count: int
    score_sum: float

    # keyword -> count within this bucket
    keyword_counts: Dict[str, int]

    # source -> count within this bucket
    source_breakdown: Dict[str, int]

    updated_at_utc: int  # when this aggregate was last updated (set by caller)

    @property
    def avg_score(self) -> float:
        return 0.0 if self.count <= 0 else (self.score_sum / self.count)

    def top_keywords(self, limit: int = 20) -> List[str]:
        if limit <= 0:
            return []
        ranked = sorted(
            self.keyword_counts.items(),
            key=lambda kv: (-kv[1], kv[0]),  # deterministic tie-break
        )
        return [w for (w, _) in ranked[:limit]]


def new_hourly_aggregate(
    *,
    ticker: str,
    hour_start_utc: int,
    hour_end_utc: int,
    updated_at_utc: int,
) -> HourlyAggregate:
    return HourlyAggregate(
        ticker=ticker,
        hour_start_utc=hour_start_utc,
        hour_end_utc=hour_end_utc,
        count=0,
        score_sum=0.0,
        keyword_counts={},
        source_breakdown={},
        updated_at_utc=updated_at_utc,
    )


def apply_sentiment_to_hourly(
    *,
    existing: Optional[HourlyAggregate],
    sentiment: SentimentResult,
    hour_start_utc: int,
    hour_end_utc: int,
    updated_at_utc: int,
    source: Optional[str] = None,
    max_keywords_tracked: int = 200,
) -> HourlyAggregate:
    """
    Pure update:
    - increments count
    - increments score_sum
    - updates keyword_counts (bounded by max_keywords_tracked)
    - updates source_breakdown
    - sets updated_at_utc

    Idempotency note:
    - This function is NOT idempotent by itself (it assumes each event is applied once).
    """

    agg = existing or new_hourly_aggregate(
        ticker=sentiment.ticker,
        hour_start_utc=hour_start_utc,
        hour_end_utc=hour_end_utc,
        updated_at_utc=updated_at_utc,
    )

    # Basic sanity: bucket should match
    if agg.ticker != sentiment.ticker:
        raise ValueError(
            f"ticker mismatch: agg={agg.ticker} sentiment={sentiment.ticker}"
        )
    if agg.hour_start_utc != hour_start_utc or agg.hour_end_utc != hour_end_utc:
        raise ValueError("hour bucket mismatch for existing aggregate")

    # Copy dicts (because dataclass is frozen; keep function pure)
    kw = dict(agg.keyword_counts)
    sb = dict(agg.source_breakdown)

    # Update keyword counts (bounded)
    for w in sentiment.keywords:
        if not w:
            continue
        w = w.strip().lower()
        if not w:
            continue

        if w in kw:
            kw[w] += 1
        else:
            # Enforce bounded keyword tracking: keep the map from growing unbounded
            if len(kw) < max_keywords_tracked:
                kw[w] = 1
            else:
                # If full, we ignore new unseen keywords (simple + deterministic)
                # (Later you can implement "space-saving" replacement if you want.)
                pass

    # Update source breakdown
    if source:
        s = source.strip().upper()
        if s:
            sb[s] = sb.get(s, 0) + 1

    return replace(
        agg,
        count=agg.count + 1,
        score_sum=agg.score_sum + float(sentiment.score),
        keyword_counts=kw,
        source_breakdown=sb,
        updated_at_utc=updated_at_utc,
    )
