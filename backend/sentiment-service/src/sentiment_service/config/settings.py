import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class KafkaSettings:
    bootstrap_servers: str
    group_id: str
    input_topic: str
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = False


@dataclass(frozen=True)
class MongoSettings:
    uri: str
    db_name: str
    hourly_collection: str
    signal_collection: str
    price_correlation_collection: str
    hourly_ttl_days: int = 7


def _get_env(name: str, default: str = None) -> str:
    val = os.getenv(name, default)
    if val is None or val.strip() == "":
        raise ValueError(f"Missing required env var: {name}")
    return val


def _get_env_int(name: str, default: str = None) -> int:
    raw = _get_env(name, default)
    try:
        return int(raw)
    except ValueError as e:
        raise ValueError(f"Env var {name} must be an int, got: {raw}") from e


def load_kafka_settings() -> KafkaSettings:
    return KafkaSettings(
        bootstrap_servers=_get_env("KAFKA_BOOTSTRAP_SERVERS"),
        group_id=_get_env("KAFKA_GROUP_ID", "sentiment-service"),
        input_topic=_get_env("KAFKA_INPUT_TOPIC", "CLEANED_EVENTS"),
        auto_offset_reset=_get_env("KAFKA_AUTO_OFFSET_RESET", "earliest"),
        enable_auto_commit=_get_env("KAFKA_ENABLE_AUTO_COMMIT", "false").lower()
        == "true",
    )


def load_mongo_settings() -> MongoSettings:
    return MongoSettings(
        uri=_get_env("MONGO_URI"),
        db_name=_get_env("MONGO_DB_NAME"),
        hourly_collection=_get_env(
            "MONGO_HOURLY_COLLECTION", "ticker_sentiment_hourly"
        ),
        signal_collection=_get_env(
            "MONGO_SIGNAL_COLLECTION", "ticker_sentiment_signal"
        ),
        price_correlation_collection=_get_env(
            "MONGO_PRICE_CORRELATION_COLLECTION", "ticker_price_correlation"
        ),
        hourly_ttl_days=_get_env_int("MONGO_HOURLY_TTL_DAYS", "7"),
    )
