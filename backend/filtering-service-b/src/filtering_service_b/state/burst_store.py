from __future__ import annotations

import logging

from redis import Redis

log = logging.getLogger(__name__)


class BurstCounterStore:
    def __init__(self, redis_client: Redis, bucket_ttl_seconds: int):
        self._redis = redis_client
        self._bucket_ttl_seconds = bucket_ttl_seconds

    @staticmethod
    def _bucket_key(ticker: str, minute_bucket_utc: int) -> str:
        return f"fsb:v1:burst:ticker:{ticker.upper()}:min:{minute_bucket_utc}"

    @staticmethod
    def _minute_bucket(epoch_seconds: int) -> int:
        return (epoch_seconds // 60) * 60

    def increment(self, ticker: str, event_time_utc: int) -> None:
        bucket = self._minute_bucket(event_time_utc)
        key = self._bucket_key(ticker, bucket)
        try:
            pipe = self._redis.pipeline(transaction=False)
            pipe.incr(key)
            pipe.expire(key, self._bucket_ttl_seconds)
            pipe.execute()
        except Exception:
            log.exception("Failed to increment burst counter ticker=%s bucket=%s", ticker, bucket)

    def get_context(
        self,
        ticker: str,
        now_utc: int,
        recent_window_minutes: int = 5,
        baseline_window_minutes: int = 30,
    ) -> dict:
        now_bucket = self._minute_bucket(now_utc)

        recent_keys = [
            self._bucket_key(ticker, now_bucket - (60 * i))
            for i in range(max(recent_window_minutes, 1))
        ]

        baseline_keys = [
            self._bucket_key(ticker, now_bucket - (60 * i))
            for i in range(max(baseline_window_minutes, 1))
        ]

        try:
            recent_vals = self._redis.mget(recent_keys)
            baseline_vals = self._redis.mget(baseline_keys)
        except Exception:
            log.exception("Failed to read burst counters ticker=%s", ticker)
            return {
                "recentCount": 0,
                "baselineCount": 0,
                "baselineAvgPerMinute": 0.0,
                "burstRatio": 0.0,
            }

        recent_count = sum(_safe_int(v) for v in recent_vals if v is not None)
        baseline_count = sum(_safe_int(v) for v in baseline_vals if v is not None)
        baseline_avg = baseline_count / float(max(baseline_window_minutes, 1))
        burst_ratio = float(recent_count) / max(baseline_avg, 1.0)

        return {
            "recentCount": recent_count,
            "baselineCount": baseline_count,
            "baselineAvgPerMinute": baseline_avg,
            "burstRatio": burst_ratio,
        }


def _safe_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
