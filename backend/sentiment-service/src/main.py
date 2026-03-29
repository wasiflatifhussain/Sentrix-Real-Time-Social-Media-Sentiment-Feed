from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from dotenv import load_dotenv

from sentiment_service.config.settings import load_kafka_settings, load_mongo_settings
from sentiment_service.domain.scoring import StubSentimentScorer
from sentiment_service.domain.signal_stub import placeholder_signal_score
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

from sentiment_service.demo_file_parser import DemoKafkaParser, DemoMongoDBParser

from sentiment_service.runner import Runner as SentimentServiceRunner

log = logging.getLogger(__name__)

SIGNAL_CHECK_INTERVAL_SECONDS = 60
SIGNAL_GRACE_SECONDS = 15 * 60


class SentimentServiceApp:
    def __init__(self) -> None:
        load_dotenv()
        configure_logging("INFO")

        self.kafka_settings = load_kafka_settings()
        self.mongo_settings = load_mongo_settings()
        self.sentiment = SentimentServiceRunner()
        self.mongo = MongoClientFactory(
            MongoClientSettings(
                uri=self.mongo_settings.uri, db_name=self.mongo_settings.db_name
            )
        )
        db = self.mongo.db()

        self.hourly_repo = HourlyRepo(
            db=db,
            collection_name=self.mongo_settings.hourly_collection,
            ttl_days=self.mongo_settings.hourly_ttl_days,
        )
        self.hourly_repo.ensure_indexes()

        self.signal_repo = SignalRepo(
            db=db, collection_name=self.mongo_settings.signal_collection
        )
        self.signal_repo.ensure_indexes()

        self.scorer = StubSentimentScorer(max_keywords=10)
        self.hourly_cache: dict[str, HourlyLevelScore] = {}
        self.hourly_additive_score_sum: dict[str, float] = {}
        self.stop_flag = threading.Event()
        self.runner = KafkaConsumerRunner(self.kafka_settings)
        self.signal_thread = threading.Thread(
            target=self._signal_updater_loop, name="signal-updater", daemon=True
        )

    @staticmethod
    def _eligible_hour_start_utc(now_utc: int, grace_seconds: int) -> int:
        t = now_utc - grace_seconds
        current_hour_start = (t // SECONDS_PER_HOUR) * SECONDS_PER_HOUR
        return current_hour_start - SECONDS_PER_HOUR

    @staticmethod
    def _coerce_epoch_seconds(value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("boolean is not a valid epoch timestamp")

        ts_raw: int
        if isinstance(value, int):
            ts_raw = value
        elif isinstance(value, float):
            ts_raw = int(value)
        elif isinstance(value, str):
            s = value.strip()
            if not s:
                return None
            try:
                ts_raw = int(float(s))
            except ValueError as e:
                raise ValueError(f"invalid epoch timestamp string: {value}") from e
        else:
            raise ValueError(f"unsupported timestamp type: {type(value)}")

        if ts_raw > 10**12:
            ts_raw = ts_raw // 1000

        if ts_raw < 0:
            raise ValueError(f"invalid negative epoch timestamp: {ts_raw}")
        return ts_raw

    @classmethod
    def _normalize_event_timestamp_seconds(cls, event: Any) -> int:
        created_ts = cls._coerce_epoch_seconds(getattr(event, "created_at_utc", None))
        if created_ts is not None:
            return created_ts

        ingested_ts = cls._coerce_epoch_seconds(
            getattr(event, "ingested_at_utc", None)
        )
        if ingested_ts is not None:
            return ingested_ts

        raise ValueError("event has neither valid created_at_utc nor ingested_at_utc")

    @staticmethod
    def _init_hourly_level_score(
        *,
        key: str,
        ticker: str,
        hour_start_utc: int,
        hour_end_utc: int,
        created_at_utc: int,
    ) -> HourlyLevelScore:
        return HourlyLevelScore(
            _id=key,
            ticker=ticker,
            createdAtUtc=created_at_utc,
            hourStartUtc=hour_start_utc,
            hourEndUtc=hour_end_utc,
            count=0,
            scoreSum=0.0,
            keywordCounts={},
            sourceBreakdown={},
            metrics={},
        )

    @staticmethod
    def _hourly_cache_key(ticker: str, hour_start_utc: int) -> str:
        return f"{ticker}|{int(hour_start_utc)}"

    @staticmethod
    def _extract_event_metrics(payload: dict[str, Any]) -> dict[str, Any]:
        metrics = payload.get("ingestorEvent", {}).get("metrics", {})
        return metrics if isinstance(metrics, dict) else {}

    def _get_or_create_hourly_level(
        self,
        *,
        ticker: str,
        hour_start_utc: int,
        hour_end_utc: int,
        created_at_utc: int,
    ) -> HourlyLevelScore:
        key = self._hourly_cache_key(ticker, hour_start_utc)
        hourly_level = self.hourly_cache.get(key)
        if hourly_level is None:
            hourly_level = self._init_hourly_level_score(
                key=key,
                ticker=ticker,
                hour_start_utc=hour_start_utc,
                hour_end_utc=hour_end_utc,
                created_at_utc=created_at_utc,
            )
            self.hourly_cache[key] = hourly_level
        return hourly_level

    @staticmethod
    def _apply_hourly_aggregation(
        hourly_level: HourlyLevelScore,
        *,
        cleaned_event: Any,
        event_score: float,
        metrics: dict[str, Any],
    ) -> dict[str, float]:
        return hourly_level.add_scored_cleaned_event(
            cleaned_event=cleaned_event,
            sentiment_score=float(event_score),
            metrics=metrics,
        )

    def _persist_hourly_aggregate(
        self,
        *,
        ticker: str,
        source: str,
        keywords: list[str],
        hour_start_utc: int,
        hour_end_utc: int,
        updated_at_utc: int,
        event_score: float,
        event_weight: float,
        hourly_level: HourlyLevelScore,
    ) -> None:
        self.hourly_repo.upsert_incremental(
            ticker=ticker,
            hour_start_utc=hour_start_utc,
            hour_end_utc=hour_end_utc,
            sentiment_score=float(event_score),
            keywords=list(keywords),
            source=source,
            updated_at_utc=updated_at_utc,
            weighted_score_increment=float(event_score) * float(event_weight),
            weight_increment=float(event_weight),
            avg_score=float(hourly_level._avgScore),
            hour_reliability=float(hourly_level.hour_reliability()),
        )

    def _signal_updater_loop(self) -> None:
        last_applied_hour: int | None = None

        while not self.stop_flag.is_set():
            try:
                now = int(time.time())
                eligible_hour_start = self._eligible_hour_start_utc(
                    now_utc=now, grace_seconds=SIGNAL_GRACE_SECONDS
                )

                log.info(
                    "Signal loop tick now=%s eligible_hour_start=%s last_applied=%s",
                    now,
                    eligible_hour_start,
                    last_applied_hour,
                )

                if last_applied_hour is None or eligible_hour_start > last_applied_hour:
                    tickers = self.hourly_repo.distinct_tickers_for_hour(
                        hour_start_utc=eligible_hour_start
                    )

                    if not tickers:
                        tickers = self.hourly_repo.distinct_tickers_recent(
                            lookback_days=self.mongo_settings.hourly_ttl_days
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
                            applied = self.signal_repo.upsert_signal_if_new_hour(
                                ticker=ticker,
                                signal_score=score,
                                as_of_hour_start_utc=eligible_hour_start,
                                updated_at_utc=now,
                                half_life_hours=None,
                            )
                            if applied:
                                applied_count += 1

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

            self.stop_flag.wait(SIGNAL_CHECK_INTERVAL_SECONDS)

    def handle(self, msg: Any) -> None:
        log.info("currently handling - %s", msg)
        payload = self.runner.decode_json(msg)
        domain_event = parse_cleaned_event(payload)

        self.sentiment.assess_event_level(domain_event)

        print(domain_event)

        try:
            event_ts_utc = self._normalize_event_timestamp_seconds(domain_event)
        except ValueError:
            log.exception(
                "Skipping event due to invalid timestamps eventId=%s created_at_utc=%s ingested_at_utc=%s",
                domain_event.event_id,
                domain_event.created_at_utc,
                domain_event.ingested_at_utc,
            )
            return

        domain_event.created_at_utc = event_ts_utc
        bucket = bucket_epoch_seconds_to_hour(event_ts_utc)
        scored = self.scorer.score(domain_event)

        now_utc = int(time.time())
        metrics = self._extract_event_metrics(payload) if isinstance(payload, dict) else {}
        event_score = float(scored.score)
        hourly_level = self._get_or_create_hourly_level(
            ticker=domain_event.ticker,
            hour_start_utc=bucket.hour_start_utc,
            hour_end_utc=bucket.hour_end_utc,
            created_at_utc=event_ts_utc,
        )
        cache_key = self._hourly_cache_key(domain_event.ticker, bucket.hour_start_utc)
        additive_score_sum = (
            float(self.hourly_additive_score_sum.get(cache_key, 0.0)) + event_score
        )
        self.hourly_additive_score_sum[cache_key] = additive_score_sum
        hourly_metrics = self._apply_hourly_aggregation(
            hourly_level,
            cleaned_event=domain_event,
            event_score=event_score,
            metrics=metrics,
        )
        self._persist_hourly_aggregate(
            ticker=domain_event.ticker,
            source=domain_event.source,
            keywords=list(scored.keywords),
            hour_start_utc=bucket.hour_start_utc,
            hour_end_utc=bucket.hour_end_utc,
            updated_at_utc=now_utc,
            event_score=event_score,
            event_weight=float(hourly_metrics["event_weight"]),
            hourly_level=hourly_level,
        )

        log.info(
            "Hourly upsert ok eventId=%s ticker=%s hourStartUtc=%s count=%s scoreSum=%s weightedScoreSum=%s weightSum=%s avgScore=%s hourReliability=%s topic=%s partition=%s offset=%s",
            domain_event.event_id,
            domain_event.ticker,
            bucket.hour_start_utc,
            hourly_level.count,
            additive_score_sum,
            hourly_level._weightedScoreSum,
            hourly_level._weightSum,
            hourly_level._avgScore,
            hourly_metrics["hour_reliability"],
            msg.topic(),
            msg.partition(),
            msg.offset(),
        )

    def run(self) -> None:
        # self.signal_thread.start()
        try:
            self.runner.start(self.handle)
        finally:
            self.stop_flag.set()
            self.mongo.close()


def main() -> None:
    SentimentServiceApp().run()

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
    runner = SentimentServiceRunner()

    dmp = DemoMongoDBParser()

    prev_hourly_levels = dmp.return_hourly_level()

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
