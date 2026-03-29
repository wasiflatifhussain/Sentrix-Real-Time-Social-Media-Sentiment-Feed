import sys
import types

sys.modules.setdefault(
    "huggingface_hub",
    types.SimpleNamespace(InferenceClient=object),
)

from main import SentimentServiceApp
from sentiment_service.objects.objects import TickerLevelScore


def test_hourly_doc_adapter_feeds_ticker_level_with_avg_score():
    first = SentimentServiceApp._hourly_doc_to_hourly_level(
        {
            "_id": "TSLA|3600",
            "ticker": "TSLA",
            "count": 10,
            "createdAtUtc": 3600,
            "hourStartUtc": 3600,
            "hourEndUtc": 7200,
            "scoreSum": 3.0,
            "avgScore": 0.5,
            "weightedScoreSum": 5.0,
            "weightSum": 10.0,
            "keywordCounts": {"earnings": 2},
            "sourceBreakdown": {"REDDIT": 10},
        }
    )
    second = SentimentServiceApp._hourly_doc_to_hourly_level(
        {
            "_id": "TSLA|7200",
            "ticker": "TSLA",
            "count": 10,
            "createdAtUtc": 7200,
            "hourStartUtc": 7200,
            "hourEndUtc": 10800,
            "scoreSum": 1.0,
            "avgScore": 0.5,
            "weightedScoreSum": 5.0,
            "weightSum": 10.0,
            "keywordCounts": {"guidance": 1},
            "sourceBreakdown": {"REDDIT": 10},
        }
    )

    ticker = TickerLevelScore(_id="TSLA", ticker="TSLA")
    ticker.update_hour_levels(first)
    ticker.update_hour_levels(second)

    assert first.scoreSum == 0.5
    assert second.scoreSum == 0.5
    assert ticker.count == 20
    assert ticker.startTimestamp == 3600
    assert ticker.endTimestamp == 10800
    assert abs(ticker.weighted_score - 0.5) < 1e-9
