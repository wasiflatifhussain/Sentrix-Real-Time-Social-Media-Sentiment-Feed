import json
import logging
from typing import Callable

from confluent_kafka import Consumer, KafkaException, Message

from sentiment_service.config.settings import KafkaSettings, build_kafka_client_config

log = logging.getLogger(__name__)


class KafkaConsumerRunner:
    def __init__(self, settings: KafkaSettings):
        self._settings = settings
        config = build_kafka_client_config(settings)
        config["group.id"] = settings.group_id
        config["auto.offset.reset"] = settings.auto_offset_reset
        config["enable.auto.commit"] = settings.enable_auto_commit
        self._consumer = Consumer(config)

    def start(self, on_message: Callable[[Message], None]) -> None:
        topic = self._settings.input_topic
        log.info("Subscribing to topic=%s group_id=%s", topic, self._settings.group_id)
        self._consumer.subscribe([topic])

        try:
            while True:
                msg = self._consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    # Non-fatal errors can happen; treat carefully
                    raise KafkaException(msg.error())

                try:
                    on_message(msg)

                    # Manual commit(ack) if auto-commit disabled
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

        return json.loads(raw_str)
