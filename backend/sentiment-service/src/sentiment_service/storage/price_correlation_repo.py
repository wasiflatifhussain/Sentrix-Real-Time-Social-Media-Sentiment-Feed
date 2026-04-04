from __future__ import annotations
from typing import Any, Optional

from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError


def _correlation_id(ticker: str, hour_start_utc: int) -> str:
    return f"{ticker}|{int(hour_start_utc)}"


def _cursor_id(name: str) -> str:
    return f"cursor:{name}"


class PriceCorrelationRepo:
    """
    Stores price-correlation stage data in a single Mongo collection.

    The collection contains two document types:
    - correlation: one row per (ticker, hourStartUtc)
    - cursor: durable checkpoint for the price-correlation stage
    """

    def __init__(self, db: Database, collection_name: str, ttl_days: int):
        self._col: Collection = db[collection_name]
        self._ttl_days = max(1, int(ttl_days))

    def ensure_indexes(self) -> None:
        self._col.create_index([("docType", 1), ("ticker", 1), ("hourStartUtc", -1)])
        self._col.create_index([("docType", 1), ("updatedAtUtc", -1)])
        self._col.create_index("expireAtUtc", expireAfterSeconds=0)

    def insert_correlation_if_absent(
        self,
        *,
        ticker: str,
        hour_start_utc: int,
        hour_end_utc: int,
        updated_at_utc: int,
        sentiment_score: Optional[float] = None,
        sentiment_volume: Optional[int] = None,
        price_open: Optional[float] = None,
        price_high: Optional[float] = None,
        price_low: Optional[float] = None,
        price_close: Optional[float] = None,
        price_change: Optional[float] = None,
        price_change_pct: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        doc_id = _correlation_id(ticker, hour_start_utc)
        expire_at_utc = int(hour_end_utc + self._ttl_days * 24 * 3600)
        doc: dict[str, Any] = {
            "_id": doc_id,
            "docType": "correlation",
            "ticker": ticker.strip().upper(),
            "hourStartUtc": int(hour_start_utc),
            "hourEndUtc": int(hour_end_utc),
            "createdAtUtc": int(updated_at_utc),
            "updatedAtUtc": int(updated_at_utc),
            "expireAtUtc": expire_at_utc,
        }

        optional_values = {
            "sentimentScore": sentiment_score,
            "sentimentVolume": sentiment_volume,
            "priceOpen": price_open,
            "priceHigh": price_high,
            "priceLow": price_low,
            "priceClose": price_close,
            "priceChange": price_change,
            "priceChangePct": price_change_pct,
        }
        for field_name, value in optional_values.items():
            if value is not None:
                doc[field_name] = value

        if metadata is not None:
            doc["metadata"] = dict(metadata)

        try:
            self._col.insert_one(doc)
            return True
        except DuplicateKeyError:
            return False

    def find_recent_by_ticker(self, *, ticker: str, limit: int = 24) -> list[dict]:
        t = (ticker or "").strip().upper()
        if not t:
            return []

        limit = max(1, int(limit))
        return list(
            self._col.find({"docType": "correlation", "ticker": t})
            .sort("hourStartUtc", -1)
            .limit(limit)
        )

    def find_one_by_hour(self, *, ticker: str, hour_start_utc: int) -> dict | None:
        t = (ticker or "").strip().upper()
        if not t:
            return None

        return self._col.find_one(
            {
                "_id": _correlation_id(t, hour_start_utc),
                "docType": "correlation",
            }
        )

    def get_cursor(self, *, name: str) -> dict | None:
        return self._col.find_one({"_id": _cursor_id(name), "docType": "cursor"})

    def get_cursor_hour(self, *, name: str) -> int | None:
        doc = self.get_cursor(name=name)
        if doc is None:
            return None
        hour_start_utc = doc.get("hourStartUtc")
        if hour_start_utc is None:
            return None
        return int(hour_start_utc)

    def advance_cursor_if_newer(
        self,
        *,
        name: str,
        hour_start_utc: int,
        updated_at_utc: int,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        cursor_id = _cursor_id(name)
        incoming_hour = int(hour_start_utc)
        now = int(updated_at_utc)

        existing = self._col.find_one({"_id": cursor_id}, {"hourStartUtc": 1})
        if existing is not None:
            existing_hour = existing.get("hourStartUtc")
            if existing_hour is not None and int(existing_hour) >= incoming_hour:
                return False

            set_ops: dict[str, Any] = {
                "docType": "cursor",
                "hourStartUtc": incoming_hour,
                "updatedAtUtc": now,
            }
            if metadata is not None:
                set_ops["metadata"] = dict(metadata)

            res = self._col.update_one(
                {
                    "_id": cursor_id,
                    "$or": [
                        {"hourStartUtc": {"$exists": False}},
                        {"hourStartUtc": {"$lt": incoming_hour}},
                    ],
                },
                {"$set": set_ops},
                upsert=False,
            )
            return res.matched_count > 0

        doc: dict[str, Any] = {
            "_id": cursor_id,
            "docType": "cursor",
            "hourStartUtc": incoming_hour,
            "updatedAtUtc": now,
            "createdAtUtc": now,
        }
        if metadata is not None:
            doc["metadata"] = dict(metadata)

        try:
            self._col.insert_one(doc)
            return True
        except DuplicateKeyError:
            res = self._col.update_one(
                {
                    "_id": cursor_id,
                    "$or": [
                        {"hourStartUtc": {"$exists": False}},
                        {"hourStartUtc": {"$lt": incoming_hour}},
                    ],
                },
                {
                    "$set": {
                        "docType": "cursor",
                        "hourStartUtc": incoming_hour,
                        "updatedAtUtc": now,
                        **({"metadata": dict(metadata)} if metadata is not None else {}),
                    }
                },
                upsert=False,
            )
            return res.matched_count > 0
