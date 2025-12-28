from __future__ import annotations

import time
from typing import Dict, List, Optional

from pymongo.collection import Collection
from pymongo.database import Database
from sentiment_service.domain.aggregation import HourlyAggregate


def _hourly_id(ticker: str, hour_start_utc: int) -> str:
    return f"{ticker}|{hour_start_utc}"


class HourlyRepo:
    """
    Persists hourly aggregates into MongoDB.

    Storage strategy:
    - store `count` and `scoreSum` as incrementals (replay-friendly building blocks)
    - store keywordCounts mapped to counts
    """

    def __init__(
        self,
        db: Database,
        collection_name: str,
        ttl_days: int,
        keywords_list_limit: int = 20,
    ):
        self._col: Collection = db[collection_name]
        self._ttl_days = ttl_days
        self._keywords_list_limit = keywords_list_limit

    def ensure_indexes(self) -> None:
        """
        TTL index: documents expire TTL seconds AFTER the value in `expireAtUtc`.
        Set expireAtUtc = hour_end_utc + TTL_window in upserts.
        This keeps a rolling window (last N days of hourly docs).
        """
        # Existing index (for per-ticker reads)
        self._col.create_index([("ticker", 1), ("hourStartUtc", -1)])

        # NEW: make "find all tickers active in a given hour" fast
        # (supports distinct_tickers_for_hour filter on hourStartUtc)
        self._col.create_index([("hourStartUtc", 1), ("ticker", 1)])

        # NEW: supports distinct_tickers_recent filter on updatedAtUtc
        self._col.create_index([("updatedAtUtc", -1)])

        # TTL index (seconds = 0 means expire at exact expireAtUtc)
        # NOTE: TTL monitor runs ~every 60 seconds; deletion isn't instantaneous.
        self._col.create_index("expireAtUtc", expireAfterSeconds=0)

    def upsert_incremental(
        self,
        *,
        ticker: str,
        hour_start_utc: int,
        hour_end_utc: int,
        sentiment_score: float,
        keywords: list[str],
        source: Optional[str],
        updated_at_utc: int,
        ttl_days: Optional[int] = None,
    ) -> None:
        """
        Atomic incremental update per event. Update hourly docs without reading them first (works great for streaming).
        """
        ttl_window_days = self._ttl_days if ttl_days is None else ttl_days
        expire_at_utc = int(hour_end_utc + ttl_window_days * 24 * 3600)

        inc_ops: Dict[str, int | float] = {
            "count": 1,
            "scoreSum": float(sentiment_score),
        }
        set_ops: Dict[str, object] = {
            "ticker": ticker,
            "hourStartUtc": int(hour_start_utc),
            "hourEndUtc": int(hour_end_utc),
            "updatedAtUtc": int(updated_at_utc),
            "expireAtUtc": int(expire_at_utc),
        }

        # Store counts for keywords (incremental)
        # keywordCounts.<kw> += 1
        for w in keywords:
            w = (w or "").strip().lower()
            if not w:
                continue
            inc_ops[f"keywordCounts.{w}"] = inc_ops.get(f"keywordCounts.{w}", 0) + 1

        # sourceBreakdown.<SRC> += 1
        if source:
            s = source.strip().upper()
            if s:
                inc_ops[f"sourceBreakdown.{s}"] = (
                    inc_ops.get(f"sourceBreakdown.{s}", 0) + 1
                )

        self._col.update_one(
            {"_id": _hourly_id(ticker, hour_start_utc)},
            {
                "$setOnInsert": {
                    "_id": _hourly_id(ticker, hour_start_utc),
                    "createdAtUtc": int(updated_at_utc),
                },
                "$set": set_ops,
                "$inc": inc_ops,
            },
            upsert=True,
        )

    def upsert_from_aggregate(self, agg: HourlyAggregate) -> None:
        """
        Optional: write a fully computed aggregate (read-modify-write style).
        This is fine for testing but in streaming, `upsert_incremental` is usually better.
        """
        doc = {
            "_id": _hourly_id(agg.ticker, agg.hour_start_utc),
            "ticker": agg.ticker,
            "hourStartUtc": int(agg.hour_start_utc),
            "hourEndUtc": int(agg.hour_end_utc),
            "count": int(agg.count),
            "scoreSum": float(agg.score_sum),
            "avgScore": float(agg.avg_score),
            "keywordCounts": dict(agg.keyword_counts),
            "keywords": agg.top_keywords(self._keywords_list_limit),
            "sourceBreakdown": dict(agg.source_breakdown),
            "updatedAtUtc": int(agg.updated_at_utc),
        }

        # expireAtUtc uses TTL index
        expire_at_utc = int(agg.hour_end_utc + self._ttl_days * 24 * 3600)
        doc["expireAtUtc"] = expire_at_utc

        self._col.update_one(
            {"_id": doc["_id"]},
            {"$set": doc, "$setOnInsert": {"createdAtUtc": int(agg.updated_at_utc)}},
            upsert=True,
        )

    # Get distinct tickers methods for signal updater from MongoDB
    def distinct_tickers_for_hour(self, *, hour_start_utc: int) -> List[str]:
        """
        Returns distinct tickers that have an hourly doc for the given hourStartUtc.
        Efficient: only hits docs for that hour window.
        """
        raw = self._col.distinct("ticker", filter={"hourStartUtc": int(hour_start_utc)})
        return [t for t in raw if isinstance(t, str) and t.strip()]

    def distinct_tickers_recent(self, *, lookback_days: int) -> List[str]:
        """
        Fallback: distinct tickers updated in recent window.
        Uses updatedAtUtc; ensures signal updater can still run even if that exact hour has no docs.
        """
        now = int(time.time())
        lookback_seconds = max(1, int(lookback_days)) * 24 * 3600
        min_updated_at = now - lookback_seconds

        raw = self._col.distinct(
            "ticker",
            filter={"updatedAtUtc": {"$gte": int(min_updated_at)}},
        )
        return [t for t in raw if isinstance(t, str) and t.strip()]

    def find_recent_by_ticker(self, *, ticker: str, hours: int) -> List[dict]:
        t = (ticker or "").strip().upper()
        if not t:
            return []

        hours = max(1, int(hours))
        now = int(time.time())
        cutoff = now - hours * 3600

        return list(
            self._col.find({"ticker": t, "hourStartUtc": {"$gte": cutoff}}).sort(
                "hourStartUtc", 1
            )  # ascending for charts
        )
