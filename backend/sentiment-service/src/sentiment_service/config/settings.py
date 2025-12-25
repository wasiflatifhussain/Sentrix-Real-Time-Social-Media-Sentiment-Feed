import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)  # Immutable configuration class
class KafkaSettings:
    bootstrap_servers: str
    group_id: str
    input_topic: str
    auto_offset_reset: str = "earliest"
    enable_auto_commit: bool = False


def _get_env(name: str, default: str | None = None) -> str:
    val = os.getenv(name, default)
    if val is None or val.strip() == "":
        raise ValueError(f"Missing required env var: {name}")
    return val


def load_kafka_settings() -> KafkaSettings:
    return KafkaSettings(
        bootstrap_servers=_get_env("KAFKA_BOOTSTRAP_SERVERS"),
        group_id=_get_env("KAFKA_GROUP_ID", "sentiment-service"),
        input_topic=_get_env("KAFKA_INPUT_TOPIC", "CLEANED_EVENTS"),
        auto_offset_reset=_get_env("KAFKA_AUTO_OFFSET_RESET", "earliest"),
        enable_auto_commit=_get_env("KAFKA_ENABLE_AUTO_COMMIT", "false").lower()
        == "true",
    )
