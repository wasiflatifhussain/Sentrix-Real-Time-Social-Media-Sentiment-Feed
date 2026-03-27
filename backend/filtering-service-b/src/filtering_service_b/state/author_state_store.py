from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from redis import Redis

log = logging.getLogger(__name__)


def _author_token(author: str) -> str:
    return hashlib.sha1(author.encode("utf-8", errors="replace")).hexdigest()


class AuthorTickerStateStore:
    def __init__(self, redis_client: Redis, ttl_seconds: int, max_items: int):
        self._redis = redis_client
        self._ttl_seconds = ttl_seconds
        self._max_items = max_items

    @staticmethod
    def _key(author_token: str, ticker: str) -> str:
        return f"fsb:v1:author:{author_token}:ticker:{ticker.upper()}:history"

    def get_recent(self, author: str, ticker: str, limit: int = 30) -> list[dict[str, Any]]:
        token = _author_token(author)
        try:
            rows = self._redis.lrange(self._key(token, ticker), 0, max(limit - 1, 0))
        except Exception:
            log.exception(
                "Failed to read author+ticker history ticker=%s author_hash=%s",
                ticker,
                token[:8],
            )
            return []
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                out.append(json.loads(row))
            except (TypeError, json.JSONDecodeError):
                log.warning(
                    "Skipping invalid author+ticker state row ticker=%s author_hash=%s",
                    ticker,
                    token[:8],
                )
                continue
        return out

    def add(self, author: str, ticker: str, payload: dict[str, Any]) -> None:
        token = _author_token(author)
        key = self._key(token, ticker)
        try:
            encoded = json.dumps(payload, ensure_ascii=True)
        except (TypeError, ValueError):
            log.exception(
                "Failed to serialize author+ticker payload ticker=%s author_hash=%s",
                ticker,
                token[:8],
            )
            return

        try:
            pipe = self._redis.pipeline(transaction=False)
            pipe.lpush(key, encoded)
            pipe.ltrim(key, 0, max(self._max_items - 1, 0))
            pipe.expire(key, self._ttl_seconds)
            pipe.execute()
        except Exception:
            log.exception(
                "Failed to write author+ticker state ticker=%s author_hash=%s",
                ticker,
                token[:8],
            )
