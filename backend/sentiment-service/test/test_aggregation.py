from sentiment_service.domain.aggregation import apply_sentiment_to_hourly
from sentiment_service.domain.models import SentimentResult


def test_apply_sentiment_creates_new_aggregate():
    s = SentimentResult(
        event_id="e1", ticker="TSLA", score=0.5, keywords=["earnings", "tsla"]
    )
    agg = apply_sentiment_to_hourly(
        existing=None,
        sentiment=s,
        hour_start_utc=1000,
        hour_end_utc=4600,
        updated_at_utc=2000,
        source="reddit",
    )
    assert agg.ticker == "TSLA"
    assert agg.count == 1
    assert abs(agg.score_sum - 0.5) < 1e-9
    assert agg.source_breakdown["REDDIT"] == 1
    assert agg.keyword_counts["earnings"] == 1


def test_apply_sentiment_updates_existing():
    s1 = SentimentResult(event_id="e1", ticker="TSLA", score=0.5, keywords=["earnings"])
    s2 = SentimentResult(
        event_id="e2", ticker="TSLA", score=-0.5, keywords=["earnings", "guidance"]
    )

    agg1 = apply_sentiment_to_hourly(
        existing=None,
        sentiment=s1,
        hour_start_utc=1000,
        hour_end_utc=4600,
        updated_at_utc=2000,
        source="reddit",
    )
    agg2 = apply_sentiment_to_hourly(
        existing=agg1,
        sentiment=s2,
        hour_start_utc=1000,
        hour_end_utc=4600,
        updated_at_utc=2100,
        source="reddit",
    )

    assert agg2.count == 2
    assert abs(agg2.score_sum - 0.0) < 1e-9
    assert agg2.keyword_counts["earnings"] == 2
    assert agg2.keyword_counts["guidance"] == 1
    assert agg2.source_breakdown["REDDIT"] == 2
