from __future__ import annotations

import logging

from redis import Redis

from filtering_service_b.config.settings import RedisSettings

log = logging.getLogger(__name__)


class RedisClient:
    def __init__(self, settings: RedisSettings):
        common_kwargs = {
            "decode_responses": True,
            "socket_timeout": 2.0,
            "socket_connect_timeout": 2.0,
            "health_check_interval": 30,
        }
        if settings.url:
            self._client = Redis.from_url(settings.url, **common_kwargs)
        else:
            self._client = Redis(
                host=settings.host,
                port=settings.port,
                db=settings.db,
                username=settings.username,
                password=settings.password,
                ssl=settings.ssl,
                **common_kwargs,
            )

    @property
    def client(self) -> Redis:
        return self._client

    def ping(self) -> bool:
        return bool(self._client.ping())

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            log.exception("Failed to close Redis client")
