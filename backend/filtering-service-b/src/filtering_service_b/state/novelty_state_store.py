from __future__ import annotations

import json
from typing import Any

from redis import Redis


class AcceptedNoveltyStateStore:
    def __init__(self, redis_client: Redis, ttl_seconds: int, max_items: int):
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds
        self._max_items = max_items

    @staticmethod
    def _key(ticker: str) -> str:
        return f"fsb:v1:ticker:{ticker.upper()}:accepted_novelty"

    def get_recent(self, ticker: str, limit: int = 30) -> list[dict[str, Any]]:
        rows = self._redis.lrange(self._key(ticker), 0, max(limit - 1, 0))
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                out.append(json.loads(row))
            except Exception:
                continue
        return out

    def add(self, ticker: str, payload: dict[str, Any]) -> None:
        key = self._key(ticker)
        encoded = json.dumps(payload, ensure_ascii=True)
        pipe = self._redis.pipeline(transaction=False)
        pipe.lpush(key, encoded)
        pipe.ltrim(key, 0, max(self._max_items - 1, 0))
        pipe.expire(key, self._ttl_seconds)
        pipe.execute()
