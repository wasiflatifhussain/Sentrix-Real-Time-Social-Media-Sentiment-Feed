from __future__ import annotations

import time
from typing import Optional

from pymongo.collection import Collection
from pymongo.database import Database


class SignalRepo:
    """
    Stores one document per ticker representing the current
    market-like sentiment signal.

    This collection is the primary serving layer for backend APIs.
    """

    def __init__(self, db: Database, collection_name: str):
        self._col: Collection = db[collection_name]

    def ensure_indexes(self) -> None:
        # _id is the ticker and already indexed.
        # Secondary indexes support operational queries and monitoring.
        self._col.create_index([("updatedAtUtc", -1)])
        self._col.create_index([("asOfHourStartUtc", -1)])

    def upsert_signal_if_new_hour(
        self,
        *,
        ticker: str,
        signal_score: float,
        as_of_hour_start_utc: int,
        updated_at_utc: Optional[int] = None,
        recent_volume: Optional[int] = None,
        keywords: Optional[list[str]] = None,
        half_life_hours: Optional[int] = None,
    ) -> bool:
        """
        Insert or update the market sentiment signal for a ticker.

        Applies only if the stored asOfHourStartUtc is missing or older than the
        provided hour. This prevents double application for the same hour.

        Returns True if an update was applied, False if skipped.
        """
        now = int(time.time()) if updated_at_utc is None else int(updated_at_utc)

        doc = {
            "_id": ticker,
            "ticker": ticker,
            "signalScore": float(signal_score),
            "asOfHourStartUtc": int(as_of_hour_start_utc),
            "updatedAtUtc": now,
        }

        if recent_volume is not None:
            doc["recentVolume"] = int(recent_volume)
        if keywords is not None:
            doc["keywords"] = keywords
        if half_life_hours is not None:
            doc["halfLifeHours"] = int(half_life_hours)

        res = self._col.update_one(
            {
                "_id": ticker,
                "$or": [
                    {"asOfHourStartUtc": {"$exists": False}},
                    {"asOfHourStartUtc": {"$lt": int(as_of_hour_start_utc)}},
                ],
            },
            {"$set": doc, "$setOnInsert": {"createdAtUtc": now}},
            upsert=True,
        )

        applied = (res.matched_count > 0) or (res.upserted_id is not None)
        return applied

    def find_by_tickers(self, tickers: list[str]) -> list[dict]:
        """
        Fetch sentiment signals for a set of tickers.
        """
        if not tickers:
            return []
        return list(self._col.find({"_id": {"$in": tickers}}))
