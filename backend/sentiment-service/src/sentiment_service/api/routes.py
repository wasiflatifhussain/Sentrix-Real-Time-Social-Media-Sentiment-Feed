from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sentiment_service.config.settings import load_mongo_settings
from sentiment_service.storage.hourly_repo import HourlyRepo
from sentiment_service.storage.mongo_client import (
    MongoClientFactory,
    MongoClientSettings,
)
from sentiment_service.storage.signal_repo import SignalRepo

router = APIRouter()


class TickerListRequest(BaseModel):
    tickers: List[str]


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
        hourly_repo = HourlyRepo(
            db=db,
            collection_name=mongo_settings.hourly_collection,
            ttl_days=mongo_settings.hourly_ttl_days,
        )

        tickers = hourly_repo.distinct_tickers_recent(
            lookback_days=mongo_settings.hourly_ttl_days
        )

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
    if not body.tickers:
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
        signal_repo = SignalRepo(
            db=db,
            collection_name=mongo_settings.signal_collection,
        )

        docs = signal_repo.find_by_tickers(body.tickers)

        signals: Dict[str, Any] = {}
        for d in docs:
            ticker = d.get("_id")
            if ticker:
                d["_id"] = str(d["_id"])
                signals[ticker] = d

        return {
            "requested": body.tickers,
            "found": len(signals),
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

        signal_repo = SignalRepo(
            db=db,
            collection_name=mongo_settings.signal_collection,
        )
        hourly_repo = HourlyRepo(
            db=db,
            collection_name=mongo_settings.hourly_collection,
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
