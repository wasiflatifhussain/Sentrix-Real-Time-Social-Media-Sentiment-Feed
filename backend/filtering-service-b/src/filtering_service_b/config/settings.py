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


def _get_env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if val is None or val.strip() == "":
        raise ValueError(f"Missing required env var: {name}")
    return val


def load_kafka_settings() -> KafkaSettings:
    return KafkaSettings(
        bootstrap_servers=_get_env("KAFKA_BOOTSTRAP_SERVERS"),
        group_id=_get_env("KAFKA_GROUP_ID", "filtering-service-b"),
        input_topic=_get_env(
            "KAFKA_INPUT_TOPIC", "sentrix.filter-service-a.cleaned"
        ),
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
