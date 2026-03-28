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
    rolling_summary_every: int = 100
    near_threshold_window: float = 0.05


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


@dataclass(frozen=True)
class ManipulationSettings:
    cross_user_enabled: bool
    cross_user_max_hamming_distance: int
    cross_user_min_matches: int
    cross_user_min_unique_authors: int
    cross_user_penalty: float
    cross_user_strong_match_threshold: int
    cross_user_strong_penalty: float
    cluster_enabled: bool
    cluster_min_matches: int
    cluster_min_unique_authors: int
    cluster_max_time_span_seconds: int
    cluster_penalty: float
    cluster_strong_match_threshold: int
    cluster_strong_penalty: float
    same_account_enabled: bool
    same_account_max_hamming_distance: int
    same_account_min_matches: int
    same_account_max_time_span_seconds: int
    same_account_penalty: float
    same_account_strong_match_threshold: int
    same_account_strong_penalty: float
    same_account_extreme_match_threshold: int
    same_account_extreme_reject_enabled: bool
    burst_enabled: bool
    burst_ratio_threshold: float
    burst_amplifier_slope: float
    burst_max_multiplier: float


@dataclass(frozen=True)
class NoveltySettings:
    enabled: bool
    max_references: int
    medium_similarity_threshold: float
    low_similarity_threshold: float
    medium_penalty: float
    low_penalty: float
    distinct_similarity_threshold: float
    distinct_boost: float
    min_references_for_distinct_boost: int


@dataclass(frozen=True)
class FinalDecisionSettings:
    keep_threshold: float


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


def _ensure_int_min(value: int, label: str, minimum: int) -> None:
    if value < minimum:
        raise ValueError(f"{label} must be >= {minimum}")


def _ensure_float_min(value: float, label: str, minimum: float) -> None:
    if value < minimum:
        raise ValueError(f"{label} must be >= {minimum}")


def _ensure_gte(value: int | float, label: str, other: int | float, other_label: str) -> None:
    if value < other:
        raise ValueError(f"{label} must be >= {other_label}")


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
    settings = AppSettings(
        log_level=_get_env("APP_LOG_LEVEL", "INFO"),
        rolling_summary_every=_get_env_int("APP_ROLLING_SUMMARY_EVERY", "100"),
        near_threshold_window=_get_env_float("APP_NEAR_THRESHOLD_WINDOW", "0.05"),
    )
    if settings.rolling_summary_every <= 0:
        raise ValueError("APP_ROLLING_SUMMARY_EVERY must be >= 1")
    if settings.near_threshold_window < 0.0:
        raise ValueError("APP_NEAR_THRESHOLD_WINDOW must be >= 0.0")
    return settings


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


def _validate_manipulation_settings(
    settings: ManipulationSettings,
) -> ManipulationSettings:
    _ensure_int_min(settings.cross_user_max_hamming_distance, "MANIPULATION_CROSS_USER_MAX_HAMMING", 0)
    _ensure_int_min(settings.cross_user_min_matches, "MANIPULATION_CROSS_USER_MIN_MATCHES", 1)
    _ensure_int_min(
        settings.cross_user_min_unique_authors,
        "MANIPULATION_CROSS_USER_MIN_UNIQUE_AUTHORS",
        1,
    )
    _ensure_float_min(settings.cross_user_penalty, "MANIPULATION_CROSS_USER_PENALTY", 0.0)
    _ensure_gte(
        settings.cross_user_strong_match_threshold,
        "MANIPULATION_CROSS_USER_STRONG_MATCHES",
        settings.cross_user_min_matches,
        "MANIPULATION_CROSS_USER_MIN_MATCHES",
    )
    _ensure_gte(
        settings.cross_user_strong_penalty,
        "MANIPULATION_CROSS_USER_STRONG_PENALTY",
        settings.cross_user_penalty,
        "MANIPULATION_CROSS_USER_PENALTY",
    )

    _ensure_int_min(settings.cluster_min_matches, "MANIPULATION_CLUSTER_MIN_MATCHES", 1)
    _ensure_int_min(
        settings.cluster_min_unique_authors,
        "MANIPULATION_CLUSTER_MIN_UNIQUE_AUTHORS",
        1,
    )
    _ensure_int_min(
        settings.cluster_max_time_span_seconds,
        "MANIPULATION_CLUSTER_MAX_TIME_SPAN_SECONDS",
        1,
    )
    _ensure_float_min(settings.cluster_penalty, "MANIPULATION_CLUSTER_PENALTY", 0.0)
    _ensure_gte(
        settings.cluster_strong_match_threshold,
        "MANIPULATION_CLUSTER_STRONG_MATCHES",
        settings.cluster_min_matches,
        "MANIPULATION_CLUSTER_MIN_MATCHES",
    )
    _ensure_gte(
        settings.cluster_strong_penalty,
        "MANIPULATION_CLUSTER_STRONG_PENALTY",
        settings.cluster_penalty,
        "MANIPULATION_CLUSTER_PENALTY",
    )

    _ensure_int_min(settings.same_account_max_hamming_distance, "MANIPULATION_SAME_ACCOUNT_MAX_HAMMING", 0)
    _ensure_int_min(settings.same_account_min_matches, "MANIPULATION_SAME_ACCOUNT_MIN_MATCHES", 1)
    _ensure_int_min(
        settings.same_account_max_time_span_seconds,
        "MANIPULATION_SAME_ACCOUNT_MAX_TIME_SPAN_SECONDS",
        1,
    )
    _ensure_float_min(settings.same_account_penalty, "MANIPULATION_SAME_ACCOUNT_PENALTY", 0.0)
    _ensure_gte(
        settings.same_account_strong_match_threshold,
        "MANIPULATION_SAME_ACCOUNT_STRONG_MATCHES",
        settings.same_account_min_matches,
        "MANIPULATION_SAME_ACCOUNT_MIN_MATCHES",
    )
    _ensure_gte(
        settings.same_account_strong_penalty,
        "MANIPULATION_SAME_ACCOUNT_STRONG_PENALTY",
        settings.same_account_penalty,
        "MANIPULATION_SAME_ACCOUNT_PENALTY",
    )
    _ensure_gte(
        settings.same_account_extreme_match_threshold,
        "MANIPULATION_SAME_ACCOUNT_EXTREME_MATCHES",
        settings.same_account_strong_match_threshold,
        "MANIPULATION_SAME_ACCOUNT_STRONG_MATCHES",
    )

    _ensure_float_min(settings.burst_ratio_threshold, "MANIPULATION_BURST_RATIO_THRESHOLD", 1.0)
    _ensure_float_min(settings.burst_amplifier_slope, "MANIPULATION_BURST_AMPLIFIER_SLOPE", 0.0)
    _ensure_float_min(settings.burst_max_multiplier, "MANIPULATION_BURST_MAX_MULTIPLIER", 1.0)
    return settings


def load_manipulation_settings() -> ManipulationSettings:
    settings = ManipulationSettings(
        cross_user_enabled=_get_env_bool("MANIPULATION_CROSS_USER_ENABLED", "true"),
        cross_user_max_hamming_distance=_get_env_int(
            "MANIPULATION_CROSS_USER_MAX_HAMMING", "5"
        ),
        cross_user_min_matches=_get_env_int("MANIPULATION_CROSS_USER_MIN_MATCHES", "2"),
        cross_user_min_unique_authors=_get_env_int(
            "MANIPULATION_CROSS_USER_MIN_UNIQUE_AUTHORS", "2"
        ),
        cross_user_penalty=_get_env_float("MANIPULATION_CROSS_USER_PENALTY", "0.20"),
        cross_user_strong_match_threshold=_get_env_int(
            "MANIPULATION_CROSS_USER_STRONG_MATCHES", "4"
        ),
        cross_user_strong_penalty=_get_env_float(
            "MANIPULATION_CROSS_USER_STRONG_PENALTY", "0.35"
        ),
        cluster_enabled=_get_env_bool("MANIPULATION_CLUSTER_ENABLED", "true"),
        cluster_min_matches=_get_env_int("MANIPULATION_CLUSTER_MIN_MATCHES", "3"),
        cluster_min_unique_authors=_get_env_int(
            "MANIPULATION_CLUSTER_MIN_UNIQUE_AUTHORS", "3"
        ),
        cluster_max_time_span_seconds=_get_env_int(
            "MANIPULATION_CLUSTER_MAX_TIME_SPAN_SECONDS", "1800"
        ),
        cluster_penalty=_get_env_float("MANIPULATION_CLUSTER_PENALTY", "0.12"),
        cluster_strong_match_threshold=_get_env_int(
            "MANIPULATION_CLUSTER_STRONG_MATCHES", "6"
        ),
        cluster_strong_penalty=_get_env_float(
            "MANIPULATION_CLUSTER_STRONG_PENALTY", "0.22"
        ),
        same_account_enabled=_get_env_bool("MANIPULATION_SAME_ACCOUNT_ENABLED", "true"),
        same_account_max_hamming_distance=_get_env_int(
            "MANIPULATION_SAME_ACCOUNT_MAX_HAMMING", "5"
        ),
        same_account_min_matches=_get_env_int("MANIPULATION_SAME_ACCOUNT_MIN_MATCHES", "2"),
        same_account_max_time_span_seconds=_get_env_int(
            "MANIPULATION_SAME_ACCOUNT_MAX_TIME_SPAN_SECONDS", "1800"
        ),
        same_account_penalty=_get_env_float("MANIPULATION_SAME_ACCOUNT_PENALTY", "0.18"),
        same_account_strong_match_threshold=_get_env_int(
            "MANIPULATION_SAME_ACCOUNT_STRONG_MATCHES", "4"
        ),
        same_account_strong_penalty=_get_env_float(
            "MANIPULATION_SAME_ACCOUNT_STRONG_PENALTY", "0.32"
        ),
        same_account_extreme_match_threshold=_get_env_int(
            "MANIPULATION_SAME_ACCOUNT_EXTREME_MATCHES", "6"
        ),
        same_account_extreme_reject_enabled=_get_env_bool(
            "MANIPULATION_SAME_ACCOUNT_EXTREME_REJECT_ENABLED", "false"
        ),
        burst_enabled=_get_env_bool("MANIPULATION_BURST_ENABLED", "true"),
        burst_ratio_threshold=_get_env_float("MANIPULATION_BURST_RATIO_THRESHOLD", "2.0"),
        burst_amplifier_slope=_get_env_float("MANIPULATION_BURST_AMPLIFIER_SLOPE", "0.25"),
        burst_max_multiplier=_get_env_float("MANIPULATION_BURST_MAX_MULTIPLIER", "1.8"),
    )
    return _validate_manipulation_settings(settings)


def _validate_novelty_settings(settings: NoveltySettings) -> NoveltySettings:
    _ensure_int_min(settings.max_references, "NOVELTY_MAX_REFERENCES", 1)
    _ensure_int_min(
        settings.min_references_for_distinct_boost,
        "NOVELTY_MIN_REFERENCES_FOR_DISTINCT_BOOST",
        1,
    )

    for label, value in (
        ("NOVELTY_MEDIUM_SIMILARITY_THRESHOLD", settings.medium_similarity_threshold),
        ("NOVELTY_LOW_SIMILARITY_THRESHOLD", settings.low_similarity_threshold),
        ("NOVELTY_DISTINCT_SIMILARITY_THRESHOLD", settings.distinct_similarity_threshold),
    ):
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{label} must be in range [0.0, 1.0]")

    _ensure_gte(
        settings.low_similarity_threshold,
        "NOVELTY_LOW_SIMILARITY_THRESHOLD",
        settings.medium_similarity_threshold,
        "NOVELTY_MEDIUM_SIMILARITY_THRESHOLD",
    )
    if settings.distinct_similarity_threshold > settings.medium_similarity_threshold:
        raise ValueError(
            "NOVELTY_DISTINCT_SIMILARITY_THRESHOLD must be <= "
            "NOVELTY_MEDIUM_SIMILARITY_THRESHOLD"
        )

    _ensure_float_min(settings.medium_penalty, "NOVELTY_MEDIUM_PENALTY", 0.0)
    _ensure_float_min(settings.low_penalty, "NOVELTY_LOW_PENALTY", 0.0)
    _ensure_gte(
        settings.low_penalty,
        "NOVELTY_LOW_PENALTY",
        settings.medium_penalty,
        "NOVELTY_MEDIUM_PENALTY",
    )
    _ensure_float_min(settings.distinct_boost, "NOVELTY_DISTINCT_BOOST", 0.0)
    return settings


def load_novelty_settings() -> NoveltySettings:
    settings = NoveltySettings(
        enabled=_get_env_bool("NOVELTY_ENABLED", "true"),
        max_references=_get_env_int("NOVELTY_MAX_REFERENCES", "20"),
        medium_similarity_threshold=_get_env_float(
            "NOVELTY_MEDIUM_SIMILARITY_THRESHOLD", "0.82"
        ),
        low_similarity_threshold=_get_env_float(
            "NOVELTY_LOW_SIMILARITY_THRESHOLD", "0.92"
        ),
        medium_penalty=_get_env_float("NOVELTY_MEDIUM_PENALTY", "0.10"),
        low_penalty=_get_env_float("NOVELTY_LOW_PENALTY", "0.20"),
        distinct_similarity_threshold=_get_env_float(
            "NOVELTY_DISTINCT_SIMILARITY_THRESHOLD", "0.45"
        ),
        distinct_boost=_get_env_float("NOVELTY_DISTINCT_BOOST", "0.03"),
        min_references_for_distinct_boost=_get_env_int(
            "NOVELTY_MIN_REFERENCES_FOR_DISTINCT_BOOST", "3"
        ),
    )
    return _validate_novelty_settings(settings)


def load_final_decision_settings() -> FinalDecisionSettings:
    keep_threshold = _get_env_float("FINAL_KEEP_THRESHOLD", "0.40")
    if not 0.0 <= keep_threshold <= 1.0:
        raise ValueError("FINAL_KEEP_THRESHOLD must be in range [0.0, 1.0]")
    return FinalDecisionSettings(keep_threshold=keep_threshold)
