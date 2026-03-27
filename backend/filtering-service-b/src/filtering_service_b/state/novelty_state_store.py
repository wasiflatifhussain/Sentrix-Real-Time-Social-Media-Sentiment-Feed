from __future__ import annotations

import json
import logging
from typing import Any

from redis import Redis

log = logging.getLogger(__name__)


class AcceptedNoveltyStateStore:
    def __init__(self, redis_client: Redis, ttl_seconds: int, max_items: int):
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds
        self._max_items = max_items

    @staticmethod
    def _key(ticker: str) -> str:
        return f"fsb:v1:ticker:{ticker.upper()}:accepted_novelty"

    def get_recent(self, ticker: str, limit: int = 30) -> list[dict[str, Any]]:
        try:
            rows = self._redis.lrange(self._key(ticker), 0, max(limit - 1, 0))
        except Exception:
            log.exception("Failed to read novelty state ticker=%s", ticker)
            return []
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                out.append(json.loads(row))
            except (TypeError, json.JSONDecodeError):
                log.warning("Skipping invalid novelty state row ticker=%s", ticker)
                continue
        return out

    def add(self, ticker: str, payload: dict[str, Any]) -> None:
        key = self._key(ticker)
        try:
            encoded = json.dumps(payload, ensure_ascii=True)
        except (TypeError, ValueError):
            log.exception("Failed to serialize novelty payload ticker=%s", ticker)
            return

        try:
            pipe = self._redis.pipeline(transaction=False)
            pipe.lpush(key, encoded)
            pipe.ltrim(key, 0, max(self._max_items - 1, 0))
            pipe.expire(key, self._ttl_seconds)
            pipe.execute()
        except Exception:
            log.exception("Failed to write novelty state ticker=%s", ticker)
