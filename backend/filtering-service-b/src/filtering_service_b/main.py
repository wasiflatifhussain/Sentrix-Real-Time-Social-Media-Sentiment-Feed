from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager
from typing import Any, TypedDict

import uvicorn
from confluent_kafka import Message
from fastapi import FastAPI

from filtering_service_b.config.settings import (
    load_app_settings,
    load_kafka_settings,
    load_manipulation_settings,
    load_novelty_settings,
    load_relevance_settings,
    load_redis_settings,
    load_state_ttl_settings,
)
from filtering_service_b.messaging.kafka_consumer import KafkaConsumerRunner
from filtering_service_b.messaging.kafka_producer import KafkaProducerClient
from filtering_service_b.messaging.schemas import CleanedEvent, parse_cleaned_event
from filtering_service_b.observability.logging import configure_logging
from filtering_service_b.pipeline.processor import FilterBSemanticProcessor, FilterDecision
from filtering_service_b.manipulation.repetition_scorer import CrossUserRepetitionScorer
from filtering_service_b.novelty.novelty_scorer import NoveltyScorer
from filtering_service_b.relevance.embedding_service import (
    SentenceTransformerEmbeddingService,
)
from filtering_service_b.relevance.relevance_scorer import TickerRelevanceScorer
from filtering_service_b.relevance.ticker_profiles import TickerProfileStore
from filtering_service_b.state.author_state_store import AuthorTickerStateStore
from filtering_service_b.state.burst_store import BurstCounterStore
from filtering_service_b.state.novelty_state_store import AcceptedNoveltyStateStore
from filtering_service_b.state.redis_client import RedisClient
from filtering_service_b.state.ticker_state_store import TickerSimilarityStateStore

log = logging.getLogger(__name__)


class StateContext(TypedDict):
    tickerSimilarity: list[dict[str, Any]]
    authorTickerHistory: list[dict[str, Any]]
    acceptedNovelty: list[dict[str, Any]]
    burst: dict[str, Any]


def _resolve_event_time_utc(created_at_utc: int | None) -> int:
    if isinstance(created_at_utc, int):
        return created_at_utc
    return int(time.time())


def _build_state_context(
    event: CleanedEvent,
    ticker_store: TickerSimilarityStateStore,
    author_store: AuthorTickerStateStore,
    novelty_store: AcceptedNoveltyStateStore,
    burst_store: BurstCounterStore,
    event_time_utc: int,
) -> StateContext:
    return {
        "tickerSimilarity": ticker_store.get_recent(event.ticker, limit=30),
        "authorTickerHistory": (
            author_store.get_recent(event.author, event.ticker, limit=20)
            if event.author
            else []
        ),
        "acceptedNovelty": novelty_store.get_recent(event.ticker, limit=20),
        "burst": burst_store.get_context(event.ticker, now_utc=event_time_utc),
    }


def _persist_runtime_state(
    event: CleanedEvent,
    decision: FilterDecision,
    ticker_store: TickerSimilarityStateStore,
    author_store: AuthorTickerStateStore,
    novelty_store: AcceptedNoveltyStateStore,
    burst_store: BurstCounterStore,
    event_time_utc: int,
) -> None:
    simhash64 = decision.signals.get("stage2SimHash")

    # Update similarity and burst state for incoming events.
    ticker_store.add(
        event.ticker,
        {
            "eventId": event.event_id,
            "author": event.author,
            "timestampUtc": event_time_utc,
            "text": event.text_normalized,
            "simHash64": simhash64,
        },
    )
    burst_store.increment(event.ticker, event_time_utc)

    # Update author+ticker history if author is present.
    if event.author:
        author_store.add(
            event.author,
            event.ticker,
            {
                "eventId": event.event_id,
                "timestampUtc": event_time_utc,
                "text": event.text_normalized,
                "simHash64": simhash64,
            },
        )

    # Update novelty memory only for kept events.
    if decision.decision == "KEEP":
        novelty_store.add(
            event.ticker,
            {
                "eventId": event.event_id,
                "timestampUtc": event_time_utc,
                "text": event.text_normalized,
                "title": event.title,
            },
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_settings = load_app_settings()
    configure_logging(app_settings.log_level)

    kafka_settings = load_kafka_settings()
    redis_settings = load_redis_settings()
    ttl_settings = load_state_ttl_settings()
    relevance_settings = load_relevance_settings()
    manipulation_settings = load_manipulation_settings()
    novelty_settings = load_novelty_settings()

    consumer = KafkaConsumerRunner(kafka_settings)
    producer = KafkaProducerClient(kafka_settings)
    ticker_profiles = TickerProfileStore.from_json(relevance_settings.ticker_profiles_path)
    embedding_service = SentenceTransformerEmbeddingService(
        model_name=relevance_settings.model_name,
        normalize_embeddings=relevance_settings.normalize_embeddings,
    )
    relevance_scorer = TickerRelevanceScorer(
        embedding_service=embedding_service,
        ticker_profiles=ticker_profiles,
        settings=relevance_settings,
    )
    cross_user_scorer = CrossUserRepetitionScorer(settings=manipulation_settings)
    novelty_scorer = NoveltyScorer(
        embedding_service=embedding_service,
        settings=novelty_settings,
    )
    processor = FilterBSemanticProcessor(
        relevance_scorer=relevance_scorer,
        cross_user_scorer=cross_user_scorer,
        novelty_scorer=novelty_scorer,
    )
    stop_event = threading.Event()

    redis_client = RedisClient(redis_settings)
    redis_client.ping()

    ticker_store = TickerSimilarityStateStore(
        redis_client=redis_client.client,
        ttl_seconds=ttl_settings.similarity_ttl_seconds,
        max_items=ttl_settings.max_list_items,
    )
    author_store = AuthorTickerStateStore(
        redis_client=redis_client.client,
        ttl_seconds=ttl_settings.author_ticker_ttl_seconds,
        max_items=ttl_settings.max_list_items,
    )
    novelty_store = AcceptedNoveltyStateStore(
        redis_client=redis_client.client,
        ttl_seconds=ttl_settings.accepted_novelty_ttl_seconds,
        max_items=ttl_settings.max_list_items,
    )
    burst_store = BurstCounterStore(
        redis_client=redis_client.client,
        bucket_ttl_seconds=ttl_settings.burst_bucket_ttl_seconds,
    )

    def handle(msg: Message) -> None:
        payload = consumer.decode_json(msg)

        try:
            event = parse_cleaned_event(payload)
            event_time_utc = _resolve_event_time_utc(event.created_at_utc)

            state_context = _build_state_context(
                event=event,
                ticker_store=ticker_store,
                author_store=author_store,
                novelty_store=novelty_store,
                burst_store=burst_store,
                event_time_utc=event_time_utc,
            )

            decision = processor.process(event, state_context=state_context)

            burst_context = state_context["burst"]
            state_signals = {
                "tickerSimilarityCount": len(state_context["tickerSimilarity"]),
                "authorTickerCount": len(state_context["authorTickerHistory"]),
                "acceptedNoveltyCount": len(state_context["acceptedNovelty"]),
                "burstRatio": burst_context.get("burstRatio", 0.0),
            }

            out = processor.build_output_envelope(
                payload,
                decision,
                state_signals=state_signals,
            )

            if decision.decision == "KEEP":
                producer.publish_filtered(out)
            else:
                producer.publish_rejected(out)

            _persist_runtime_state(
                event=event,
                decision=decision,
                ticker_store=ticker_store,
                author_store=author_store,
                novelty_store=novelty_store,
                burst_store=burst_store,
                event_time_utc=event_time_utc,
            )

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
        try:
            producer.close()
        except Exception:
            log.exception("Failed to close Kafka producer cleanly")
        try:
            redis_client.close()
        except Exception:
            log.exception("Failed to close Redis client cleanly")
        log.info("Filtering Service B worker stopped")


def create_app() -> FastAPI:
    return FastAPI(title="Filtering Service B", version="0.1.0", lifespan=lifespan)


app = create_app()


if __name__ == "__main__":
    uvicorn.run("filtering_service_b.main:app", host="0.0.0.0", port=8012, reload=False)
