from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OneHourCandle:
    symbol: str
    start_ts: int
    end_ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class FinnhubClientConfig:
    api_key: str
    base_url: str
    timeout_seconds: float = 10.0


class FinnhubClient:
    """
    Thin Finnhub REST client.
    """

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValueError("Finnhub API key is required")

        self._config = FinnhubClientConfig(
            api_key=api_key.strip(),
            base_url=(base_url or self.BASE_URL).rstrip("/"),
            timeout_seconds=float(timeout_seconds),
        )

    @property
    def base_url(self) -> str:
        return self._config.base_url

    def _get_json(
        self,
        path: str,
        *,
        params: Mapping[str, object] | None = None,
    ) -> dict[str, Any] | list[Any]:
        query_params: dict[str, object] = dict(params or {})
        query_params["token"] = self._config.api_key
        query_string = urlencode(
            {
                key: value.isoformat() if isinstance(value, date) else value
                for key, value in query_params.items()
                if value is not None
            }
        )
        url = f"{self._config.base_url}/{path.lstrip('/')}"
        if query_string:
            url = f"{url}?{query_string}"

        request = Request(url=url, method="GET")

        try:
            with urlopen(request, timeout=self._config.timeout_seconds) as response:
                payload = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.exception(
                "Finnhub HTTP error path=%s status=%s body=%s",
                path,
                exc.code,
                body,
            )
            raise
        except URLError:
            logger.exception("Finnhub network error path=%s", path)
            raise

        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            logger.exception("Finnhub returned invalid JSON path=%s", path)
            raise

    def quote(self, symbol: str) -> dict[str, Any]:
        return self._ensure_dict(
            self._get_json("quote", params={"symbol": symbol}),
            endpoint="quote",
        )

    def company_profile(self, symbol: str) -> dict[str, Any]:
        return self._ensure_dict(
            self._get_json("stock/profile2", params={"symbol": symbol}),
            endpoint="stock/profile2",
        )

    def company_news(
        self,
        symbol: str,
        *,
        from_date: date | str,
        to_date: date | str,
    ) -> list[dict[str, Any]]:
        raw = self._get_json(
            "company-news",
            params={
                "symbol": symbol,
                "from": from_date,
                "to": to_date,
            },
        )
        if not isinstance(raw, list):
            raise TypeError("Finnhub company-news response must be a list")
        return [item for item in raw if isinstance(item, dict)]

    def symbol_lookup(self, query: str) -> dict[str, Any]:
        return self._ensure_dict(
            self._get_json("search", params={"q": query}),
            endpoint="search",
        )

    def stock_candles(
        self,
        *,
        symbol: str,
        resolution: str | int,
        from_ts: int,
        to_ts: int,
    ) -> dict[str, Any]:
        return self._ensure_dict(
            self._get_json(
                "stock/candle",
                params={
                    "symbol": symbol,
                    "resolution": str(resolution),
                    "from": int(from_ts),
                    "to": int(to_ts),
                },
            ),
            endpoint="stock/candle",
        )

    def get_recent_hourly_candles(
        self,
        *,
        symbol: str,
        lookback_hours: int = 2,
    ) -> list[dict[str, Any]]:
        now_ts = int(time.time())
        from_ts = now_ts - max(1, int(lookback_hours)) * 3600
        payload = self.stock_candles(
            symbol=symbol,
            resolution=60,
            from_ts=from_ts,
            to_ts=now_ts,
        )
        return self._normalize_candle_payload(payload, symbol=symbol)

    @staticmethod
    def _ensure_dict(
        value: dict[str, Any] | list[Any],
        *,
        endpoint: str,
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise TypeError(f"Finnhub {endpoint} response must be an object")
        return value

    @staticmethod
    def _normalize_candle_payload(
        payload: dict[str, Any],
        *,
        symbol: str,
    ) -> list[dict[str, Any]]:
        status = payload.get("s")
        if status != "ok":
            return []

        opens = payload.get("o", [])
        highs = payload.get("h", [])
        lows = payload.get("l", [])
        closes = payload.get("c", [])
        volumes = payload.get("v", [])
        timestamps = payload.get("t", [])

        size = min(
            len(opens),
            len(highs),
            len(lows),
            len(closes),
            len(volumes),
            len(timestamps),
        )
        candles: list[dict[str, Any]] = []
        for idx in range(size):
            start_ts = int(timestamps[idx])
            candles.append(
                {
                    "symbol": symbol,
                    "timestamp": start_ts,
                    "start_ts": start_ts,
                    "end_ts": start_ts + 3600,
                    "open": float(opens[idx]),
                    "high": float(highs[idx]),
                    "low": float(lows[idx]),
                    "close": float(closes[idx]),
                    "volume": float(volumes[idx]),
                }
            )
        return candles
