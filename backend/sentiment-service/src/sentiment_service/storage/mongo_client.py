from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    db_name: str


class MongoClientFactory:
    """
    Owns the MongoClient lifecycle.
    In prod, keep one client per process and reuse it (thread-safe).
    """

    def __init__(self, settings: MongoSettings):
        self._settings = settings
        self._client: Optional[MongoClient] = None

    def connect(self) -> MongoClient:
        if self._client is None:
            # ServerSelectionTimeout keeps startup failures fast and obvious.
            self._client = MongoClient(
                self._settings.uri, serverSelectionTimeoutMS=5000
            )
            # Force a ping so bad URIs fail immediately
            self._client.admin.command("ping")
        return self._client

    def db(self) -> Database:
        client = self.connect()
        return client[self._settings.db_name]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
