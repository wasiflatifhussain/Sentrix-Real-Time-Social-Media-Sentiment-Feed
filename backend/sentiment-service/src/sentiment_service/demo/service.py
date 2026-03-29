from __future__ import annotations

import json
import logging

from sentiment_service.demo.file_parser import DemoKafkaParser, DemoMongoDBParser
from sentiment_service.demo.runner import Runner as SentimentServiceRunner
from sentiment_service.objects.objects import TickerLevelScore

logger = logging.getLogger(__name__)


def write_hourly(hourly: list) -> None:
    content: list[dict] = list()

    for h in hourly:
        logger.info("Writing hourly level data for ticker=%s hour=%s", h.ticker, h.hourStartUtc)
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

    with open("./hourly-level-score-result.json", "w") as f:
        f.write(json.dumps(content, indent=4))

    logger.info("Done with writing hourly-level-score-result.json")


def write_ticker(ticker: list[TickerLevelScore]) -> None:
    content: list[dict] = list()

    for t in ticker:
        logger.info("Writing ticker level data for ticker=%s", t.ticker)
        content.append(
            dict(
                _id=t._id,
                ticker=t.ticker,
                count=t.count,
                absoluteScore=t.absolute_score,
                reliability=t.reliability,
                weightedScore=t.weighted_score,
                startTimeUtc=t.startTimestamp,
                endTimeUtc=t.endTimestamp,
                dequeSize=len(t.hour_levels),
            )
        )

    with open("./ticker-level-score-result.json", "w") as f:
        f.write(json.dumps(content, indent=4))


def sentiment_service() -> None:
    runner = SentimentServiceRunner()

    dmp = DemoMongoDBParser()
    prev_hourly_levels = dmp.return_hourly_level()

    for level in prev_hourly_levels:
        runner.run_ticker_level(level)

    dkp = DemoKafkaParser()
    datas = dkp.read_file()

    events: list = list()
    for data in datas[400:500]:
        events.append(runner.run_event_level(data))

    for event in events:
        runner.run_hourly_level(event)
    hourlys = runner.return_hourly_level()

    for hourly in hourlys:
        runner.run_ticker_level(hourly)

    tickers = runner.return_ticker_level()
    logger.info("Demo sentiment service produced %s ticker results", len(tickers))
