import logging

from sentiment_service.config.settings import load_kafka_settings
from sentiment_service.messaging.kafka_consumer import KafkaConsumerRunner
from sentiment_service.messaging.schemas import parse_cleaned_event
from sentiment_service.observability.logging import configure_logging

log = logging.getLogger(__name__)


def main() -> None:
    configure_logging("INFO")
    settings = load_kafka_settings()

    runner = KafkaConsumerRunner(settings)

    def handle(msg):
        payload = runner.decode_json(msg)
        event = parse_cleaned_event(payload)

        # For now: log to prove consumption works
        log.info(
            "Consumed eventId=%s ticker=%s source=%s entityType=%s topic=%s partition=%s offset=%s key=%s",
            event.event_id,
            event.ticker,
            event.source,
            event.entity_type,
            msg.topic(),
            msg.partition(),
            msg.offset(),
            (msg.key().decode("utf-8", "replace") if msg.key() else None),
        )

    runner.start(handle)


if __name__ == "__main__":
    main()
