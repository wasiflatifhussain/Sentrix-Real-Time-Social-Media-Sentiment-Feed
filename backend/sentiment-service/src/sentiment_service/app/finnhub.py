from __future__ import annotations

import argparse
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from sentiment_service.clients.finnhub_client import FinnhubClient
from sentiment_service.config.settings import MongoSettings, load_mongo_settings
from sentiment_service.storage.hourly_repo import HourlyRepo
from sentiment_service.storage.mongo_client import MongoClientFactory, MongoClientSettings
from sentiment_service.storage.price_correlation_repo import PriceCorrelationRepo
from sentiment_service.utils.time import SECONDS_PER_HOUR

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Company:
    ticker: str
    company: str
    enabled: bool
    queries: tuple[str, ...]
    symbol: str | None = None


class FinnhubCompanyConfigParser:
    def __init__(
        self,
        input_file: str | Path = "src/sentiment_service/config/finnhub_companies.json",
    ) -> None:
        self.input_file_path = Path(input_file)

    def read_file(self) -> list[dict[str, Any]]:
        with self.input_file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("Finnhub company config must be a JSON array")
        return [row for row in data if isinstance(row, dict)]

    def return_company_list(self, *, enabled_only: bool = True) -> list[Company]:
        companies: list[Company] = []
        for row in self.read_file():
            company = self._construct_company(row)
            if enabled_only and not company.enabled:
                continue
            companies.append(company)
        return companies

    @staticmethod
    def _construct_company(row: dict[str, Any]) -> Company:
        ticker = str(row.get("ticker", "")).strip().upper()
        symbol = str(row.get("symbol", ticker)).strip().upper() or ticker
        company_name = str(row.get("company", ticker)).strip() or ticker
        enabled = bool(row.get("enabled", True))
        queries_raw = row.get("queries", [])
        queries = tuple(
            str(query).strip()
            for query in queries_raw
            if isinstance(query, str) and query.strip()
        )

        if not ticker:
            raise ValueError("Each company row must include a non-empty ticker")

        return Company(
            ticker=ticker,
            company=company_name,
            enabled=enabled,
            queries=queries,
            symbol=symbol,
        )


class FinnhubRunner:
    DEFAULT_CONFIG_PATH = "src/sentiment_service/config/finnhub_companies.json"
    DEFAULT_CURSOR_NAME = "price_correlation"
    DEFAULT_GRACE_SECONDS = 15 * 60
    DEFAULT_TTL_DAYS = 7

    def __init__(
        self,
        *,
        api_key: str,
        mongo_settings: MongoSettings | None = None,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        timeout_seconds: float = 10.0,
        price_correlation_ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> None:
        self.client = FinnhubClient(
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        self.config_parser = FinnhubCompanyConfigParser(config_path)
        self.mongo_settings = mongo_settings or load_mongo_settings()
        self.mongo = MongoClientFactory(
            MongoClientSettings(
                uri=self.mongo_settings.uri,
                db_name=self.mongo_settings.db_name,
            )
        )
        db = self.mongo.db()
        self.hourly_repo = HourlyRepo(
            db=db,
            collection_name=self.mongo_settings.hourly_collection,
            ttl_days=self.mongo_settings.hourly_ttl_days,
        )
        self.price_correlation_repo = PriceCorrelationRepo(
            db=db,
            collection_name=self.mongo_settings.price_correlation_collection,
            ttl_days=price_correlation_ttl_days,
        )
        self.price_correlation_repo.ensure_indexes()

    @staticmethod
    def _eligible_hour_start_utc(now_utc: int, grace_seconds: int) -> int:
        t = now_utc - grace_seconds
        current_hour_start = (t // SECONDS_PER_HOUR) * SECONDS_PER_HOUR
        return current_hour_start - SECONDS_PER_HOUR

    @staticmethod
    def _resolve_company_symbol(company: Company) -> str:
        resolved_symbol = (company.symbol or company.ticker).strip().upper()
        if not resolved_symbol:
            raise ValueError("company must include a symbol or ticker")
        return resolved_symbol

    def return_company_list(self, *, enabled_only: bool = True) -> list[Company]:
        return self.config_parser.return_company_list(enabled_only=enabled_only)

    def load_hourly_sentiment_for_hour(
        self,
        *,
        ticker: str,
        hour_start_utc: int,
    ) -> dict[str, Any] | None:
        return self.hourly_repo.find_one_for_hour(
            ticker=ticker,
            hour_start_utc=hour_start_utc,
        )

    def get_next_hour_to_process(
        self,
        *,
        now_utc: int | None = None,
        grace_seconds: int | None = None,
        cursor_name: str | None = None,
    ) -> int | None:
        now = int(time.time()) if now_utc is None else int(now_utc)
        resolved_grace_seconds = (
            self.DEFAULT_GRACE_SECONDS
            if grace_seconds is None
            else int(grace_seconds)
        )
        resolved_cursor_name = cursor_name or self.DEFAULT_CURSOR_NAME
        eligible_hour_start = self._eligible_hour_start_utc(
            now_utc=now,
            grace_seconds=resolved_grace_seconds,
        )
        cursor_hour = self.get_cursor_hour(name=resolved_cursor_name)
        return self.hourly_repo.find_next_available_hour_start(
            max_hour_start_utc=eligible_hour_start,
            after_hour_start_utc=cursor_hour,
        )

    def load_next_hourly_batch(
        self,
        *,
        now_utc: int | None = None,
        grace_seconds: int | None = None,
        cursor_name: str | None = None,
    ) -> tuple[int, list[dict[str, Any]]] | None:
        next_hour_start = self.get_next_hour_to_process(
            now_utc=now_utc,
            grace_seconds=grace_seconds,
            cursor_name=cursor_name,
        )
        if next_hour_start is None:
            return None

        tickers = self.hourly_repo.distinct_tickers_for_hour(
            hour_start_utc=next_hour_start
        )
        hourly_docs: list[dict[str, Any]] = []
        for ticker in tickers:
            hourly_doc = self.load_hourly_sentiment_for_hour(
                ticker=ticker,
                hour_start_utc=next_hour_start,
            )
            if hourly_doc is not None:
                hourly_docs.append(hourly_doc)
        return next_hour_start, hourly_docs

    def get_current_hour_candle(self, *, company: Company) -> dict[str, Any] | None:
        candles = self.client.get_recent_hourly_candles(
            symbol=self._resolve_company_symbol(company),
            lookback_hours=2,
        )
        if not candles:
            return None
        return candles[-1]

    def get_an_hour_ago(self, *, company: Company) -> dict[str, Any] | None:
        candles = self.client.get_recent_hourly_candles(
            symbol=self._resolve_company_symbol(company),
            lookback_hours=2,
        )
        if len(candles) < 2:
            return None
        return candles[-2]

    def get_cursor_hour(
        self,
        *,
        name: str | None = None,
    ) -> int | None:
        return self.price_correlation_repo.get_cursor_hour(
            name=name or self.DEFAULT_CURSOR_NAME
        )

    def advance_cursor_if_newer(
        self,
        *,
        hour_start_utc: int,
        updated_at_utc: int,
        name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        return self.price_correlation_repo.advance_cursor_if_newer(
            name=name or self.DEFAULT_CURSOR_NAME,
            hour_start_utc=hour_start_utc,
            updated_at_utc=updated_at_utc,
            metadata=metadata,
        )

    def close(self) -> None:
        self.mongo.close()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a direct Finnhub check")
    parser.add_argument(
        "--mode",
        choices=["quote", "profile", "news", "search", "current-hour", "previous-hour"],
        default="quote",
    )
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--query", default="Apple")
    parser.add_argument("--from-date", dest="from_date", default=str(date.today()))
    parser.add_argument("--to-date", dest="to_date", default=str(date.today()))
    parser.add_argument("--api-key-env", default="FINNHUB_API_KEY")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    load_dotenv()
    args = _parse_args()

    api_key = os.getenv(args.api_key_env)
    if not api_key:
        raise ValueError(f"Missing required env var: {args.api_key_env}")

    runner = FinnhubRunner(
        api_key=api_key,
        timeout_seconds=args.timeout_seconds,
    )

    try:
        if args.mode == "quote":
            result = runner.client.quote(args.symbol)
        elif args.mode == "profile":
            result = runner.client.company_profile(args.symbol)
        elif args.mode == "news":
            result = runner.client.company_news(
                args.symbol,
                from_date=args.from_date,
                to_date=args.to_date,
            )
        elif args.mode == "search":
            result = runner.client.symbol_lookup(args.query)
        else:
            company = Company(
                ticker=args.symbol.upper(),
                symbol=args.symbol.upper(),
                company=args.symbol.upper(),
                enabled=True,
                queries=(),
            )
            if args.mode == "current-hour":
                result = runner.get_current_hour_candle(company=company)
            else:
                result = runner.get_an_hour_ago(company=company)
    finally:
        runner.close()

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
