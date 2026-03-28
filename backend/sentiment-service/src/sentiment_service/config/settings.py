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
    hourly_ttl_days: int = 7


def _get_env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if val is None or val.strip() == "":
        raise ValueError(f"Missing required env var: {name}")
    return val


def _get_env_int(name: str, default: str | None = None) -> int:
    raw = _get_env(name, default)
    try:
        return int(raw)
    except ValueError as e:
        raise ValueError(f"Env var {name} must be an int, got: {raw}") from e


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
        hourly_ttl_days=_get_env_int("MONGO_HOURLY_TTL_DAYS", "7"),
    )
