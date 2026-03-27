from __future__ import annotations

from redis import Redis


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
        pipe = self._redis.pipeline(transaction=False)
        pipe.incr(key)
        pipe.expire(key, self._bucket_ttl_seconds)
        pipe.execute()

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

        recent_vals = self._redis.mget(recent_keys)
        baseline_vals = self._redis.mget(baseline_keys)

        recent_count = sum(int(v) for v in recent_vals if v is not None)
        baseline_count = sum(int(v) for v in baseline_vals if v is not None)
        baseline_avg = baseline_count / float(max(baseline_window_minutes, 1))
        burst_ratio = float(recent_count) / max(baseline_avg, 1.0)

        return {
            "recentCount": recent_count,
            "baselineCount": baseline_count,
            "baselineAvgPerMinute": baseline_avg,
            "burstRatio": burst_ratio,
        }
