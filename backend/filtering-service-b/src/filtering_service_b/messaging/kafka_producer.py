import json
import logging

from confluent_kafka import Producer

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
        self._producer.flush(5.0)

    def _publish(self, topic: str, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self._producer.produce(topic=topic, value=data)
        self._producer.flush(5.0)
        log.debug("Published message topic=%s bytes=%s", topic, len(data))
