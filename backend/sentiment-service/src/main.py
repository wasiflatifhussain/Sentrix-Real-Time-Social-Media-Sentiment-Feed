from __future__ import annotations

import json
import logging
import threading
import time
import os

from dotenv import load_dotenv

from sentiment_service.config.settings import load_kafka_settings, load_mongo_settings
from sentiment_service.domain.scoring import StubSentimentScorer
from sentiment_service.domain.signal_stub import placeholder_signal_score
from sentiment_service.messaging.adapters import to_domain_event
from sentiment_service.messaging.kafka_consumer import KafkaConsumerRunner
from sentiment_service.messaging.schemas import parse_cleaned_event
from sentiment_service.objects.objects import HourlyLevelScore, TickerLevelScore
from sentiment_service.observability.logging import configure_logging
from sentiment_service.storage.hourly_repo import HourlyRepo
from sentiment_service.storage.mongo_client import (
    MongoClientFactory,
    MongoClientSettings,
)
from sentiment_service.storage.signal_repo import SignalRepo
from sentiment_service.utils.time import SECONDS_PER_HOUR, bucket_epoch_seconds_to_hour

from sentiment_service.llm_connector import FinbertClient
from sentiment_service.demo_file_parser import DemoKafkaParser, DemoMongoDBParser

from sentiment_service.runner import Runner as SentimentServiceRunner

log = logging.getLogger(__name__)

SIGNAL_CHECK_INTERVAL_SECONDS = 60
SIGNAL_GRACE_SECONDS = 15 * 60


def _eligible_hour_start_utc(now_utc: int, grace_seconds: int) -> int:
    """
    Returns the previous hourStartUtc considered closed after a grace window.
    Example: now=15:17 and grace=15m -> eligible hourStartUtc=14:00.
    """
    t = now_utc - grace_seconds
    current_hour_start = (t // SECONDS_PER_HOUR) * SECONDS_PER_HOUR
    return current_hour_start - SECONDS_PER_HOUR


def main() -> None:
    load_dotenv()
    configure_logging("INFO")

    kafka_settings = load_kafka_settings()
    mongo_settings = load_mongo_settings()

    # print(mongo_settings)

    sentiment = SentimentServiceRunner()

    mongo = MongoClientFactory(
        MongoClientSettings(uri=mongo_settings.uri, db_name=mongo_settings.db_name)
    )
    db = mongo.db()

    hourly_repo = HourlyRepo(
        db=db,
        collection_name=mongo_settings.hourly_collection,
        ttl_days=mongo_settings.hourly_ttl_days,
    )
    hourly_repo.ensure_indexes()

    signal_repo = SignalRepo(db=db, collection_name=mongo_settings.signal_collection)
    signal_repo.ensure_indexes()

    scorer = StubSentimentScorer(max_keywords=10)

    stop_flag = threading.Event()

    def signal_updater_loop() -> None:
        """
        Placeholder signal updater.

        Reads tickers from Mongo hourly aggregates instead of in-memory tickers seen in this process.
        This means signals can be written after restart even when no new Kafka messages arrive.
        """
        last_applied_hour: int | None = None

        # Runs every SIGNAL_CHECK_INTERVAL_SECONDS seconds until stop_flag is set
        while not stop_flag.is_set():
            try:
                now = int(time.time())
                eligible_hour_start = _eligible_hour_start_utc(
                    now_utc=now, grace_seconds=SIGNAL_GRACE_SECONDS
                )

                log.info(
                    "Signal loop tick now=%s eligible_hour_start=%s last_applied=%s",
                    now,
                    eligible_hour_start,
                    last_applied_hour,
                )

                # Prevent double application for the same hour
                if last_applied_hour is None or eligible_hour_start > last_applied_hour:
                    # Most efficient: only tickers that actually have docs for this hour
                    tickers = hourly_repo.distinct_tickers_for_hour(
                        hour_start_utc=eligible_hour_start
                    )

                    # Fallback: if hour has no docs (quiet hour / timing), still allow signal updates
                    if not tickers:
                        tickers = hourly_repo.distinct_tickers_recent(
                            lookback_days=mongo_settings.hourly_ttl_days
                        )

                    log.info(
                        "Signal loop tickers_found=%s hourStartUtc=%s",
                        len(tickers),
                        eligible_hour_start,
                    )

                    if tickers:
                        applied_count = 0
                        for ticker in tickers:
                            score = placeholder_signal_score(
                                ticker=ticker, hour_start_utc=eligible_hour_start
                            )
                            # applied = signal_repo.upsert_signal_if_new_hour(
                            #     ticker=ticker,
                            #     signal_score=score,
                            #     as_of_hour_start_utc=eligible_hour_start,
                            #     updated_at_utc=now,
                            #     half_life_hours=None,
                            # )
                            # if applied:
                            #     applied_count += 1

                        log.info(
                            "Signal placeholder applied hourStartUtc=%s tickers=%s applied=%s",
                            eligible_hour_start,
                            len(tickers),
                            applied_count,
                        )
                    else:
                        log.info(
                            "Signal loop: no tickers found (hourStartUtc=%s)",
                            eligible_hour_start,
                        )

                    last_applied_hour = eligible_hour_start

            except Exception:
                log.exception("Signal updater loop error")

            stop_flag.wait(
                SIGNAL_CHECK_INTERVAL_SECONDS
            )  # Used stop flag instead of time.sleep

    signal_thread = threading.Thread(
        target=signal_updater_loop, name="signal-updater", daemon=True
    )
    # signal_thread.start()

    runner = KafkaConsumerRunner(kafka_settings)

    def handle(msg):
        log.info(f"currently handling - {msg}")
        payload = runner.decode_json(msg)
        domain_event = parse_cleaned_event(payload)
        # domain_event = to_domain_event(transport_event)

        sentiment.assess_event_level(domain_event)

        print(domain_event)

        bucket = bucket_epoch_seconds_to_hour(domain_event.created_at_utc)
        scored = scorer.score(domain_event)

        now_utc = int(time.time())

        # hourly_repo.upsert_incremental(
        #     ticker=domain_event.ticker,
        #     hour_start_utc=bucket.hour_start_utc,
        #     hour_end_utc=bucket.hour_end_utc,
        #     sentiment_score=float(scored.score),
        #     keywords=list(scored.keywords),
        #     source=domain_event.source,
        #     updated_at_utc=now_utc,
        # )

        # print(domain_event)
        # print(payload)
        

        log.info(
            "Hourly upsert ok eventId=%s ticker=%s hourStartUtc=%s topic=%s partition=%s offset=%s",
            domain_event.event_id,
            domain_event.ticker,
            bucket.hour_start_utc,
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )

        return

    try:
        runner.start(handle)
    finally:
        stop_flag.set()
        mongo.close()

''' MAIN FUNCTION '''
def write_hourly(hourly: list) -> None:
    content: list[dict] = list()
    
    for h in hourly:
        print(f"Writing hourly level data for {h}")
        content.append(
            dict(
                _id=h._id,
                count=h.count,
                createdAtUtc=h.createdAtUtc,
                hourStartUtc=h.hourStartUtc,
                hourEndUtc=h.hourEndUtc,
                keywordCounts=h.keywordCounts,
                scoreSum=h.scoreSum,
                weightedScoreSum=h._weightedScoreSum,
                weightSum=h._weightSum,
                avgScore=h._avgScore,
                sourceBreakdown=h.sourceBreakdown,
                ticker=h.ticker,
                metrics=h.metrics,
            )
        )

    with open("./hourly-level-score-result.json", 'w') as f:
        f.write(json.dumps(content, indent=4))

    print("Done with the write the houly-level-score-result.json")
    return

def write_ticker(ticker: list[TickerLevelScore]) -> None:
    content: list[dict] = list()
    
    for t in ticker:
        print(f"Writing ticker level data for {t.ticker}")
        content.append(
            dict(
                _id = t._id,
                ticker = t.ticker,
                count = t.count,
                absoluteScore = t.absolute_score,
                reliability = t.reliability,
                weightedScore = t.weighted_score,
                startTimeUtc = t.startTimestamp,
                endTimeUtc = t.endTimestamp,
                dequeSize = len(t.hour_levels),
            )
        )

    with open("./ticker-level-score-result.json", 'w') as f:
        f.write(json.dumps(content, indent=4))
    
    return

def sentiment_service() -> None:
    ###############
    # Set UP
    ###############
    runner: Runner = Runner()

    dmp = DemoMongoDBParser()

    prev_hourly_levels: list[HourlyLevelScore] = dmp.return_hourly_level()

    for level in prev_hourly_levels:
        runner.run_ticker_level(level)
    ###############
    # Set UP END
    ###############

    # Kafka
    dkp = DemoKafkaParser() # replace this with actual kafka connection
    datas = dkp.read_file()

    # Runner

    events: list = list()
    for data in datas[400:500]:
        events.append(runner.run_event_level(data))
        # event.calculate() 
    # dkp.write_event(events) -> 24/7 -> deployable -> kafka -> static one time thingy
    
    
    for event in events:
        runner.run_hourly_level(event)
    hourlys = runner.return_hourly_level()

    # write_hourly(hourlys)
    
    for hourly in hourlys:
        runner.run_ticker_level(hourly)

    tickers = runner.return_ticker_level()

    print(tickers) # for printing only
    # write_ticker(tickers) # for writing to json.

    return

if __name__ == "__main__":
    # sentiment_service()
    main()

