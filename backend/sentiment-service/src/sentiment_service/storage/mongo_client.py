from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pymongo import MongoClient
from pymongo.database import Database


@dataclass(frozen=True)
class MongoClientSettings:
    uri: str
    db_name: str


class MongoClientFactory:
    """
    Owns the MongoClient lifecycle.

    One MongoClient per process is standard; MongoClient is thread-safe.
    """

    def __init__(self, settings: MongoClientSettings):
        self._settings = settings
        self._client: Optional[MongoClient] = None

    def connect(self) -> MongoClient:
        if self._client is None:
            self._client = MongoClient(
                self._settings.uri,
                serverSelectionTimeoutMS=5000,
            )
            self._client.admin.command("ping")
        return self._client

    def db(self) -> Database:
        client = self.connect()
        return client[self._settings.db_name]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
