import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class KafkaSettings:
    bootstrap_servers: str
    group_id: str
    input_topic: str
    filtered_topic: str
    rejected_topic: str
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = False


@dataclass(frozen=True)
class AppSettings:
    log_level: str = "INFO"


@dataclass(frozen=True)
class RedisSettings:
    host: str
    port: int
    db: int
    password: str | None
    ssl: bool


@dataclass(frozen=True)
class StateTtlSettings:
    similarity_ttl_seconds: int
    author_ticker_ttl_seconds: int
    accepted_novelty_ttl_seconds: int
    burst_bucket_ttl_seconds: int
    max_list_items: int


def _get_env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if val is None or val.strip() == "":
        raise ValueError(f"Missing required env var: {name}")
    return val


def _get_optional_env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name, default)
    if val is None:
        return None
    val = val.strip()
    return val if val else None


def _get_env_int(name: str, default: str | None = None) -> int:
    raw = _get_env(name, default)
    try:
        return int(raw)
    except ValueError as ex:
        raise ValueError(f"Env var {name} must be int, got: {raw}") from ex


def _get_env_bool(name: str, default: str | None = None) -> bool:
    raw = _get_env(name, default).strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def load_kafka_settings() -> KafkaSettings:
    return KafkaSettings(
        bootstrap_servers=_get_env("KAFKA_BOOTSTRAP_SERVERS"),
        group_id=_get_env("KAFKA_GROUP_ID", "filtering-service-b"),
        input_topic=_get_env("KAFKA_INPUT_TOPIC", "sentrix.filter-service-a.cleaned"),
        filtered_topic=_get_env(
            "KAFKA_FILTERED_TOPIC", "sentrix.filter-service-b.filtered"
        ),
        rejected_topic=_get_env(
            "KAFKA_REJECTED_TOPIC", "sentrix.filter-service-b.rejected"
        ),
        auto_offset_reset=_get_env("KAFKA_AUTO_OFFSET_RESET", "earliest"),
        enable_auto_commit=_get_env("KAFKA_ENABLE_AUTO_COMMIT", "false").lower()
        == "true",
    )


def load_app_settings() -> AppSettings:
    return AppSettings(log_level=_get_env("APP_LOG_LEVEL", "INFO"))


def load_redis_settings() -> RedisSettings:
    return RedisSettings(
        host=_get_env("REDIS_HOST", "localhost"),
        port=_get_env_int("REDIS_PORT", "6379"),
        db=_get_env_int("REDIS_DB", "0"),
        password=_get_optional_env("REDIS_PASSWORD"),
        ssl=_get_env_bool("REDIS_SSL", "false"),
    )


def load_state_ttl_settings() -> StateTtlSettings:
    return StateTtlSettings(
        similarity_ttl_seconds=_get_env_int("STATE_SIMILARITY_TTL_SECONDS", "21600"),
        author_ticker_ttl_seconds=_get_env_int(
            "STATE_AUTHOR_TICKER_TTL_SECONDS", "43200"
        ),
        accepted_novelty_ttl_seconds=_get_env_int(
            "STATE_ACCEPTED_NOVELTY_TTL_SECONDS", "86400"
        ),
        burst_bucket_ttl_seconds=_get_env_int("STATE_BURST_BUCKET_TTL_SECONDS", "7200"),
        max_list_items=_get_env_int("STATE_MAX_LIST_ITEMS", "200"),
    )
