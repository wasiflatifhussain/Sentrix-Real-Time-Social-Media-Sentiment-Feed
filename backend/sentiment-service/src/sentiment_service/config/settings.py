import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class KafkaSettings:
    bootstrap_servers: str
    group_id: str
    input_topic: str
    security_protocol: str
    sasl_mechanism: str | None
    sasl_username: str | None
    sasl_password: str | None
    ssl_ca_location: str | None
    client_id: str | None
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


@dataclass(frozen=True)
class KeywordSettings:
    extractor_mode: str
    model_name: str
    normalize_embeddings: bool
    top_n: int
    max_final_keywords: int
    ngram_min: int
    ngram_max: int
    use_mmr: bool
    diversity: float
    refiner_mode: str
    llm_model: str
    llm_max_candidates: int
    llm_temperature: float


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


def _get_env_bool(name: str, default: str | None = None) -> bool:
    raw = _get_env(name, default).strip().lower()
    return raw in {"1", "true", "yes", "y", "on"}


def _get_env_float(name: str, default: str | None = None) -> float:
    raw = _get_env(name, default)
    try:
        return float(raw)
    except ValueError as e:
        raise ValueError(f"Env var {name} must be a float, got: {raw}") from e


def _get_optional_env(name: str, default: str | None = None) -> str | None:
    val = os.getenv(name, default)
    if val is None:
        return None
    val = val.strip()
    return val if val else None


def load_kafka_settings() -> KafkaSettings:
    return KafkaSettings(
        bootstrap_servers=_get_env("KAFKA_BOOTSTRAP_SERVERS"),
        group_id=_get_env("KAFKA_GROUP_ID", "sentiment-service"),
        input_topic=_get_env("KAFKA_INPUT_TOPIC", "sentrix.filter-service-b.filtered"),
        security_protocol=_get_env("KAFKA_SECURITY_PROTOCOL", "PLAINTEXT"),
        sasl_mechanism=_get_optional_env("KAFKA_SASL_MECHANISM"),
        sasl_username=_get_optional_env("KAFKA_SASL_USERNAME"),
        sasl_password=_get_optional_env("KAFKA_SASL_PASSWORD"),
        ssl_ca_location=_get_optional_env("KAFKA_SSL_CA_LOCATION"),
        client_id=_get_optional_env("KAFKA_CLIENT_ID"),
        auto_offset_reset=_get_env("KAFKA_AUTO_OFFSET_RESET", "earliest"),
        enable_auto_commit=_get_env("KAFKA_ENABLE_AUTO_COMMIT", "false").lower()
        == "true",
    )


def build_kafka_client_config(settings: KafkaSettings) -> dict[str, str | bool]:
    config: dict[str, str | bool] = {
        "bootstrap.servers": settings.bootstrap_servers,
        "security.protocol": settings.security_protocol,
    }
    if settings.client_id:
        config["client.id"] = settings.client_id
    if settings.sasl_mechanism:
        config["sasl.mechanism"] = settings.sasl_mechanism
    if settings.sasl_username:
        config["sasl.username"] = settings.sasl_username
    if settings.sasl_password:
        config["sasl.password"] = settings.sasl_password
    if settings.ssl_ca_location:
        config["ssl.ca.location"] = settings.ssl_ca_location
    return config


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


def load_keyword_settings() -> KeywordSettings:
    settings = KeywordSettings(
        extractor_mode=_get_env("KEYWORD_EXTRACTOR_MODE", "keybert").strip().lower(),
        model_name=_get_env("KEYBERT_MODEL_NAME", "all-MiniLM-L6-v2"),
        normalize_embeddings=_get_env_bool(
            "KEYBERT_NORMALIZE_EMBEDDINGS",
            "true",
        ),
        top_n=_get_env_int("KEYBERT_TOP_N", "20"),
        max_final_keywords=_get_env_int("KEYWORD_MAX_FINAL", "6"),
        ngram_min=_get_env_int("KEYBERT_NGRAM_MIN", "1"),
        ngram_max=_get_env_int("KEYBERT_NGRAM_MAX", "3"),
        use_mmr=_get_env_bool("KEYBERT_USE_MMR", "true"),
        diversity=_get_env_float("KEYBERT_DIVERSITY", "0.4"),
        refiner_mode=_get_env("KEYWORD_REFINER_MODE", "llm").strip().lower(),
        llm_model=_get_env("KEYWORD_LLM_MODEL", "qwen/qwen-2.5-7b-instruct"),
        llm_max_candidates=_get_env_int("KEYWORD_LLM_MAX_CANDIDATES", "15"),
        llm_temperature=_get_env_float("KEYWORD_LLM_TEMPERATURE", "0.0"),
    )
    if settings.top_n <= 0:
        raise ValueError("KEYBERT_TOP_N must be >= 1")
    if settings.max_final_keywords <= 0:
        raise ValueError("KEYWORD_MAX_FINAL must be >= 1")
    if settings.llm_max_candidates <= 0:
        raise ValueError("KEYWORD_LLM_MAX_CANDIDATES must be >= 1")
    if settings.ngram_min <= 0:
        raise ValueError("KEYBERT_NGRAM_MIN must be >= 1")
    if settings.ngram_max < settings.ngram_min:
        raise ValueError("KEYBERT_NGRAM_MAX must be >= KEYBERT_NGRAM_MIN")
    if settings.diversity < 0.0:
        raise ValueError("KEYBERT_DIVERSITY must be >= 0.0")
    if settings.llm_temperature < 0.0:
        raise ValueError("KEYWORD_LLM_TEMPERATURE must be >= 0.0")
    return settings
