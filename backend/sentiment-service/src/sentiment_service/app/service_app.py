from __future__ import annotations

import logging
import threading
import time
from typing import Any

from dotenv import load_dotenv

from sentiment_service.config.settings import load_kafka_settings, load_mongo_settings
from sentiment_service.domain.scoring import StubSentimentScorer
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
from sentiment_service.demo.runner import Runner as SentimentServiceRunner

log = logging.getLogger(__name__)

SIGNAL_CHECK_INTERVAL_SECONDS = 60
SIGNAL_GRACE_SECONDS = 15 * 60
TICKER_LEVEL_WINDOW_HOURS = 168


class SentimentServiceApp:
    def __init__(self) -> None:
        load_dotenv()
        configure_logging("INFO")
        log.info("Initializing sentiment service application")

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
        self.last_applied_signal_hour: int | None = None
        self.stop_flag = threading.Event()
        self.runner = KafkaConsumerRunner(self.kafka_settings)
        self.signal_thread = threading.Thread(
            target=self._signal_updater_loop, name="signal-updater", daemon=True
        )
        log.info(
            "Sentiment service initialized hourly_collection=%s signal_collection=%s",
            self.mongo_settings.hourly_collection,
            self.mongo_settings.signal_collection,
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

    @staticmethod
    def _hourly_doc_to_hourly_level(doc: dict[str, Any]) -> HourlyLevelScore:
        count = int(doc.get("count", 0) or 0)
        avg_score = doc.get("avgScore")
        score_sum = float(doc.get("scoreSum", 0.0) or 0.0)
        if avg_score is None:
            avg_score = (score_sum / count) if count > 0 else 0.0

        return HourlyLevelScore(
            _id=str(doc.get("_id", "")),
            count=count,
            createdAtUtc=int(doc.get("createdAtUtc", 0) or 0),
            hourStartUtc=int(doc.get("hourStartUtc", 0) or 0),
            hourEndUtc=int(doc.get("hourEndUtc", 0) or 0),
            keywordCounts=dict(doc.get("keywordCounts", {}) or {}),
            scoreSum=float(avg_score),
            sourceBreakdown=dict(doc.get("sourceBreakdown", {}) or {}),
            ticker=str(doc.get("ticker", "")),
            metrics=dict(doc.get("metrics", {}) or {}),
            _weightedScoreSum=float(doc.get("weightedScoreSum", 0.0) or 0.0),
            _weightSum=float(doc.get("weightSum", 0.0) or 0.0),
            _avgScore=float(avg_score),
        )

    def _build_ticker_level(
        self,
        *,
        ticker: str,
        as_of_hour_start_utc: int,
    ) -> TickerLevelScore | None:
        hourly_docs = self.hourly_repo.find_by_ticker_up_to_hour(
            ticker=ticker,
            hour_start_utc=as_of_hour_start_utc,
            limit_hours=TICKER_LEVEL_WINDOW_HOURS,
        )
        if not hourly_docs:
            return None

        ticker_level = TickerLevelScore(_id=ticker, ticker=ticker)
        for hourly_doc in hourly_docs:
            ticker_level.update_hour_levels(self._hourly_doc_to_hourly_level(hourly_doc))
        return ticker_level

    def _persist_ticker_signal(
        self,
        *,
        ticker_level: TickerLevelScore,
        as_of_hour_start_utc: int,
        updated_at_utc: int,
    ) -> bool:
        return self.signal_repo.upsert_signal_if_new_hour(
            ticker=ticker_level.ticker,
            signal_score=float(ticker_level.weighted_score),
            as_of_hour_start_utc=as_of_hour_start_utc,
            updated_at_utc=updated_at_utc,
            recent_volume=int(ticker_level.count),
            half_life_hours=24,
            absolute_score=float(ticker_level.absolute_score),
            reliability=float(ticker_level.reliability),
            weighted_score=float(ticker_level.weighted_score),
            start_time_utc=int(ticker_level.startTimestamp),
            end_time_utc=int(ticker_level.endTimestamp),
        )

    def _update_signals_for_eligible_hour(self, *, now_utc: int) -> None:
        eligible_hour_start = self._eligible_hour_start_utc(
            now_utc=now_utc, grace_seconds=SIGNAL_GRACE_SECONDS
        )
        if (
            self.last_applied_signal_hour is not None
            and eligible_hour_start <= self.last_applied_signal_hour
        ):
            return

        tickers = self.hourly_repo.distinct_tickers_for_hour(
            hour_start_utc=eligible_hour_start
        )
        log.info(
            "Ticker update check hourStartUtc=%s tickers_found=%s",
            eligible_hour_start,
            len(tickers),
        )
        if not tickers:
            return

        applied_count = 0
        for ticker in tickers:
            ticker_level = self._build_ticker_level(
                ticker=ticker,
                as_of_hour_start_utc=eligible_hour_start,
            )
            if ticker_level is None:
                continue
            applied = self._persist_ticker_signal(
                ticker_level=ticker_level,
                as_of_hour_start_utc=eligible_hour_start,
                updated_at_utc=now_utc,
            )
            if applied:
                applied_count += 1

        self.last_applied_signal_hour = eligible_hour_start
        log.info(
            "Ticker update applied hourStartUtc=%s tickers=%s applied=%s",
            eligible_hour_start,
            len(tickers),
            applied_count,
        )

    def _signal_updater_loop(self) -> None:
        while not self.stop_flag.is_set():
            try:
                now = int(time.time())
                self._update_signals_for_eligible_hour(now_utc=now)
            except Exception:
                log.exception("Signal updater loop error")

            self.stop_flag.wait(SIGNAL_CHECK_INTERVAL_SECONDS)

    def handle(self, msg: Any) -> None:
        log.info("currently handling - %s", msg)
        payload = self.runner.decode_json(msg)
        domain_event = parse_cleaned_event(payload)

        self.sentiment.assess_event_level(domain_event)
        log.info(
            "Event scored eventId=%s ticker=%s source=%s createdAtUtc=%s label=%s score=%s conf=%s",
            domain_event.event_id,
            domain_event.ticker,
            domain_event.source,
            domain_event.created_at_utc,
            domain_event.label,
            domain_event.absolute_score,
            domain_event.conf,
        )

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
        log.info("Starting signal updater thread")
        self.signal_thread.start()
        try:
            log.info("Starting Kafka consumer loop")
            self.runner.start(self.handle)
        finally:
            self.stop_flag.set()
            log.info("Stopping sentiment service application")
            self.mongo.close()
