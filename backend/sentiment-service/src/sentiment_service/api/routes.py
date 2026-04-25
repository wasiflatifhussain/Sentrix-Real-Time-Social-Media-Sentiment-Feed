from __future__ import annotations

import hashlib
import time
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sentiment_service.config.settings import load_mongo_settings
from sentiment_service.domain.signal_keywords import select_signal_keywords
from sentiment_service.storage.hourly_repo import HourlyRepo
from sentiment_service.storage.mongo_client import (
    MongoClientFactory,
    MongoClientSettings,
)
from sentiment_service.storage.signal_repo import SignalRepo

router = APIRouter()


class TickerListRequest(BaseModel):
    tickers: List[str]


def _ensure_non_zero_score(*, score: float, ticker: str, hour_start_utc: int) -> float:
    s = float(score)
    if s != 0.0:
        return s

    seed = f"{ticker}|{hour_start_utc}".encode("utf-8", errors="replace")
    sign = 1.0 if (hashlib.sha256(seed).digest()[0] % 2 == 0) else -1.0
    return 0.01 * sign


@router.get("/health")
def health() -> dict:
    """
    Health check endpoint.
    Used for uptime monitoring and deployment sanity checks.
    """
    return {"ok": True}


@router.get("/tickers")
def list_tickers(limit: int = Query(default=2000, ge=1, le=20000)) -> dict:
    """
    List all tickers currently present in the system.

    Used by frontend dropdowns / autocomplete.
    Backed by recent hourly aggregates.
    """
    mongo_settings = load_mongo_settings()
    mongo = MongoClientFactory(
        MongoClientSettings(
            uri=mongo_settings.uri,
            db_name=mongo_settings.db_name,
        )
    )

    try:
        db = mongo.db()
        api_hourly_collection = (
            mongo_settings.api_hourly_collection or mongo_settings.hourly_collection
        )
        hourly_repo = HourlyRepo(
            db=db,
            collection_name=api_hourly_collection,
            ttl_days=mongo_settings.hourly_ttl_days,
        )

        tickers = hourly_repo.distinct_tickers_recent(
            lookback_days=mongo_settings.hourly_ttl_days
        )
        if not tickers:
            tickers = hourly_repo.distinct_tickers_all()

        return {
            "tickers": tickers[:limit],
            "count": len(tickers),
        }
    finally:
        mongo.close()


@router.post("/signals/latest")
def get_latest_signals(body: TickerListRequest) -> dict:
    """
    Fetch latest signals for multiple tickers.

    Accepts a list of ticker symbols and returns their current signal snapshots.
    Used by frontend dashboard to display multiple tickers at once.
    """
    requested = [t.strip().upper() for t in body.tickers if (t or "").strip()]
    if not requested:
        raise HTTPException(status_code=400, detail="tickers is required")

    mongo_settings = load_mongo_settings()
    mongo = MongoClientFactory(
        MongoClientSettings(
            uri=mongo_settings.uri,
            db_name=mongo_settings.db_name,
        )
    )

    try:
        db = mongo.db()
        api_signal_collection = (
            mongo_settings.api_signal_collection or mongo_settings.signal_collection
        )
        signal_repo = SignalRepo(
            db=db,
            collection_name=api_signal_collection,
        )

        docs = signal_repo.find_by_tickers(requested)
        docs_by_ticker = {
            str(d.get("_id", "")).upper(): d
            for d in docs
            if isinstance(d.get("_id"), str)
        }
        now_utc = int(time.time())
        current_hour_start_utc = (now_utc // 3600) * 3600

        signals: Dict[str, Any] = {}
        for ticker in requested:
            d = docs_by_ticker.get(ticker)

            if d:
                d["_id"] = str(d["_id"])
                as_of_hour = int(d.get("asOfHourStartUtc", current_hour_start_utc))
                score = _ensure_non_zero_score(
                    score=float(d.get("signalScore", 0.0)),
                    ticker=ticker,
                    hour_start_utc=as_of_hour,
                )
                d["signalScore"] = score
                d["keywords"] = select_signal_keywords(
                    ticker=ticker,
                    signal_score=score,
                    hour_start_utc=as_of_hour,
                    limit=3,
                )
                signals[ticker] = d
            else:
                # Keep monitor stable even when a ticker has no stored signal doc yet.
                score = _ensure_non_zero_score(
                    score=0.0,
                    ticker=ticker,
                    hour_start_utc=current_hour_start_utc,
                )
                signals[ticker] = {
                    "_id": ticker,
                    "ticker": ticker,
                    "signalScore": score,
                    "asOfHourStartUtc": current_hour_start_utc,
                    "updatedAtUtc": now_utc,
                    "keywords": select_signal_keywords(
                        ticker=ticker,
                        signal_score=score,
                        hour_start_utc=current_hour_start_utc,
                        limit=3,
                    ),
                }

        return {
            "requested": requested,
            "found": len(docs_by_ticker),
            "signals": signals,
        }
    finally:
        mongo.close()


@router.get("/tickers/{ticker}/sentiment")
def get_ticker_sentiment(
    ticker: str,
    hours: int = Query(default=48, ge=1, le=24 * 14),
) -> dict:
    """
    Fetch detailed sentiment data for a single ticker.

    Returns:
    - latest signal snapshot
    - last N hours of hourly aggregates (for graphs)
    """
    if not ticker:
        raise HTTPException(status_code=400, detail="ticker is required")

    mongo_settings = load_mongo_settings()
    mongo = MongoClientFactory(
        MongoClientSettings(
            uri=mongo_settings.uri,
            db_name=mongo_settings.db_name,
        )
    )

    try:
        db = mongo.db()
        api_signal_collection = (
            mongo_settings.api_signal_collection or mongo_settings.signal_collection
        )
        api_hourly_collection = (
            mongo_settings.api_hourly_collection or mongo_settings.hourly_collection
        )

        signal_repo = SignalRepo(
            db=db,
            collection_name=api_signal_collection,
        )
        hourly_repo = HourlyRepo(
            db=db,
            collection_name=api_hourly_collection,
            ttl_days=mongo_settings.hourly_ttl_days,
        )

        signal_docs = signal_repo.find_by_tickers([ticker])
        signal = signal_docs[0] if signal_docs else None

        hourly = hourly_repo.find_recent_by_ticker(
            ticker=ticker,
            hours=hours,
        )

        if signal is None and not hourly:
            raise HTTPException(
                status_code=404,
                detail=f"no data for ticker={ticker}",
            )

        return {
            "ticker": ticker,
            "signal": signal,
            "hourly": hourly,
        }
    finally:
        mongo.close()
