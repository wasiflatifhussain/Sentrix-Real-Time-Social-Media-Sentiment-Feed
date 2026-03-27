import json
import logging

from confluent_kafka import KafkaException, Producer

from filtering_service_b.config.settings import KafkaSettings

log = logging.getLogger(__name__)


class KafkaProducerClient:
    def __init__(self, settings: KafkaSettings):
        self._settings = settings
        self._producer = Producer({"bootstrap.servers": settings.bootstrap_servers})

    def publish_filtered(self, payload: dict) -> None:
        self._publish(self._settings.filtered_topic, payload)

    def publish_rejected(self, payload: dict) -> None:
        self._publish(self._settings.rejected_topic, payload)

    def close(self) -> None:
        try:
            remaining = self._producer.flush(5.0)
            if remaining:
                log.warning("Kafka producer close flush timed out with %s undelivered message(s)", remaining)
        except Exception:
            log.exception("Kafka producer close failed")

    def _publish(self, topic: str, payload: dict) -> None:
        try:
            data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        except (TypeError, ValueError) as ex:
            raise ValueError(f"Failed to serialize payload for topic={topic}") from ex

        try:
            self._producer.produce(topic=topic, value=data)
            undelivered = self._producer.flush(5.0)
            if undelivered:
                raise RuntimeError(
                    f"Kafka flush timeout topic={topic} undelivered={undelivered}"
                )
        except KafkaException as ex:
            raise RuntimeError(f"Kafka publish failed for topic={topic}") from ex
        except BufferError as ex:
            raise RuntimeError(f"Kafka producer queue full for topic={topic}") from ex

        log.debug("Published message topic=%s bytes=%s", topic, len(data))
