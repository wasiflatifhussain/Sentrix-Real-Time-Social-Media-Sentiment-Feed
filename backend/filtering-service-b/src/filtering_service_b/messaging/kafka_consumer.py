import json
import logging
from threading import Event
from typing import Callable

from confluent_kafka import Consumer, Message

from filtering_service_b.config.settings import KafkaSettings

log = logging.getLogger(__name__)


class KafkaConsumerRunner:
    def __init__(self, settings: KafkaSettings):
        self._settings = settings
        self._consumer = Consumer(
            {
                "bootstrap.servers": settings.bootstrap_servers,
                "group.id": settings.group_id,
                "auto.offset.reset": settings.auto_offset_reset,
                "enable.auto.commit": settings.enable_auto_commit,
            }
        )

    def start(self, on_message: Callable[[Message], None], stop_event: Event) -> None:
        topic = self._settings.input_topic
        log.info("Subscribing to topic=%s group_id=%s", topic, self._settings.group_id)
        self._consumer.subscribe([topic])

        try:
            while not stop_event.is_set():
                msg = self._consumer.poll(1.0)
                if msg is None:
                    continue

                if msg.error():
                    log.error("Kafka poll error: %s", msg.error())
                    continue

                try:
                    on_message(msg)

                    # Commit only after handler publishes successfully
                    if not self._settings.enable_auto_commit:
                        self._consumer.commit(message=msg, asynchronous=False)
                except Exception:
                    log.exception(
                        "Failed processing message topic=%s partition=%s offset=%s",
                        msg.topic(),
                        msg.partition(),
                        msg.offset(),
                    )
        except KeyboardInterrupt:
            log.info("Shutdown requested (Ctrl+C).")
        finally:
            log.info("Closing Kafka consumer.")
            self._consumer.close()

    @staticmethod
    def decode_json(msg: Message) -> dict:
        raw = msg.value()
        if raw is None:
            raise ValueError("Kafka message has null value")

        if isinstance(raw, (bytes, bytearray)):
            raw_str = raw.decode("utf-8", errors="replace")
        else:
            raw_str = str(raw)

        try:
            parsed = json.loads(raw_str)
        except json.JSONDecodeError as ex:
            raise ValueError("Kafka message is not valid JSON") from ex

        if not isinstance(parsed, dict):
            raise ValueError("Kafka message JSON root must be an object")
        return parsed
