from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from filtering_service_b.config.settings import load_app_settings, load_kafka_settings
from filtering_service_b.messaging.kafka_consumer import KafkaConsumerRunner
from filtering_service_b.messaging.kafka_producer import KafkaProducerClient
from filtering_service_b.messaging.schemas import parse_cleaned_event
from filtering_service_b.observability.logging import configure_logging
from filtering_service_b.pipeline.processor import FilterBPhase1Processor, FilterDecision

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings = load_app_settings()
    configure_logging(app_settings.log_level)

    kafka_settings = load_kafka_settings()
    consumer = KafkaConsumerRunner(kafka_settings)
    producer = KafkaProducerClient(kafka_settings)
    processor = FilterBPhase1Processor()
    stop_event = threading.Event()

    def handle(msg) -> None:
        payload = consumer.decode_json(msg)

        try:
            event = parse_cleaned_event(payload)
            decision = processor.process(event)
            out = processor.build_output_envelope(payload, decision)

            if decision.decision == "KEEP":
                producer.publish_filtered(out)
            else:
                producer.publish_rejected(out)

            log.info(
                "Processed eventId=%s ticker=%s decision=%s score=%.3f topic=%s partition=%s offset=%s",
                event.event_id,
                event.ticker,
                decision.decision,
                decision.credibility_score,
                msg.topic(),
                msg.partition(),
                msg.offset(),
            )
        except Exception as ex:
            # If parsing/processing fails, route a reject envelope and keep pipeline alive.
            reject = FilterDecision(
                decision="REJECT",
                credibility_score=0.0,
                decision_reasons=["INVALID_INPUT"],
            )
            out = processor.build_output_envelope(payload, reject, filter_reason="INVALID_INPUT")
            producer.publish_rejected(out)
            log.exception("Routed INVALID_INPUT to rejected topic: %s", ex)

    worker = threading.Thread(
        target=consumer.start,
        args=(handle, stop_event),
        name="filtering-service-b-consumer",
        daemon=True,
    )

    worker.start()
    log.info("Filtering Service B worker started")

    try:
        yield
    finally:
        stop_event.set()
        worker.join(timeout=10)
        producer.close()
        log.info("Filtering Service B worker stopped")


def create_app() -> FastAPI:
    return FastAPI(title="Filtering Service B", version="0.1.0", lifespan=lifespan)


app = create_app()


if __name__ == "__main__":
    uvicorn.run("filtering_service_b.main:app", host="0.0.0.0", port=8012, reload=False)
