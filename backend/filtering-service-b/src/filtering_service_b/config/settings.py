import os
from dataclasses import dataclass
from pathlib import Path

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


@dataclass(frozen=True)
class RelevanceSettings:
    model_name: str
    ticker_profiles_path: str
    strong_similarity_threshold: float
    medium_similarity_threshold: float
    low_similarity_threshold: float
    strong_relevance_boost: float
    medium_relevance_penalty: float
    low_relevance_penalty: float
    reject_unknown_ticker_profile: bool
    normalize_embeddings: bool


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


def _get_env_float(name: str, default: str | None = None) -> float:
    raw = _get_env(name, default)
    try:
        return float(raw)
    except ValueError as ex:
        raise ValueError(f"Env var {name} must be float, got: {raw}") from ex


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


def _default_ticker_profiles_path() -> str:
    current = Path(__file__).resolve()
    relative = Path("backend/ingestor-service/src/main/resources/tickers.json")
    for parent in current.parents:
        candidate = parent / relative
        if candidate.is_file():
            return str(candidate)
    raise ValueError(
        "Unable to locate default tickers.json. Set RELEVANCE_TICKER_PROFILES_PATH explicitly."
    )


def _validate_relevance_settings(settings: RelevanceSettings) -> RelevanceSettings:
    if settings.strong_similarity_threshold < settings.medium_similarity_threshold:
        raise ValueError(
            "RELEVANCE_STRONG_SIMILARITY_THRESHOLD must be >= "
            "RELEVANCE_MEDIUM_SIMILARITY_THRESHOLD"
        )
    if settings.medium_similarity_threshold < settings.low_similarity_threshold:
        raise ValueError(
            "RELEVANCE_MEDIUM_SIMILARITY_THRESHOLD must be >= "
            "RELEVANCE_LOW_SIMILARITY_THRESHOLD"
        )

    for label, value in (
        ("RELEVANCE_STRONG_SIMILARITY_THRESHOLD", settings.strong_similarity_threshold),
        ("RELEVANCE_MEDIUM_SIMILARITY_THRESHOLD", settings.medium_similarity_threshold),
        ("RELEVANCE_LOW_SIMILARITY_THRESHOLD", settings.low_similarity_threshold),
    ):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{label} must be in range [0.0, 1.0]")

    if settings.strong_relevance_boost < 0.0:
        raise ValueError("RELEVANCE_STRONG_BOOST must be >= 0.0")
    if settings.medium_relevance_penalty < 0.0:
        raise ValueError("RELEVANCE_MEDIUM_PENALTY must be >= 0.0")
    if settings.low_relevance_penalty < 0.0:
        raise ValueError("RELEVANCE_LOW_PENALTY must be >= 0.0")

    ticker_path = Path(settings.ticker_profiles_path).expanduser().resolve()
    if not ticker_path.is_file():
        raise ValueError(f"Ticker profiles file not found: {ticker_path}")

    return RelevanceSettings(
        model_name=settings.model_name,
        ticker_profiles_path=str(ticker_path),
        strong_similarity_threshold=settings.strong_similarity_threshold,
        medium_similarity_threshold=settings.medium_similarity_threshold,
        low_similarity_threshold=settings.low_similarity_threshold,
        strong_relevance_boost=settings.strong_relevance_boost,
        medium_relevance_penalty=settings.medium_relevance_penalty,
        low_relevance_penalty=settings.low_relevance_penalty,
        reject_unknown_ticker_profile=settings.reject_unknown_ticker_profile,
        normalize_embeddings=settings.normalize_embeddings,
    )


def load_relevance_settings() -> RelevanceSettings:
    settings = RelevanceSettings(
        model_name=_get_env("RELEVANCE_MODEL_NAME", "all-MiniLM-L6-v2"),
        ticker_profiles_path=_get_env(
            "RELEVANCE_TICKER_PROFILES_PATH", _default_ticker_profiles_path()
        ),
        strong_similarity_threshold=_get_env_float(
            "RELEVANCE_STRONG_SIMILARITY_THRESHOLD", "0.58"
        ),
        medium_similarity_threshold=_get_env_float(
            "RELEVANCE_MEDIUM_SIMILARITY_THRESHOLD", "0.45"
        ),
        low_similarity_threshold=_get_env_float("RELEVANCE_LOW_SIMILARITY_THRESHOLD", "0.30"),
        strong_relevance_boost=_get_env_float("RELEVANCE_STRONG_BOOST", "0.02"),
        medium_relevance_penalty=_get_env_float("RELEVANCE_MEDIUM_PENALTY", "0.15"),
        low_relevance_penalty=_get_env_float("RELEVANCE_LOW_PENALTY", "0.40"),
        reject_unknown_ticker_profile=_get_env_bool(
            "RELEVANCE_REJECT_UNKNOWN_TICKER_PROFILE", "true"
        ),
        normalize_embeddings=_get_env_bool("RELEVANCE_NORMALIZE_EMBEDDINGS", "true"),
    )
    return _validate_relevance_settings(settings)
