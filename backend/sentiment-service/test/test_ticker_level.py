import sys
import types

sys.modules.setdefault(
    "huggingface_hub",
    types.SimpleNamespace(InferenceClient=object),
)
sys.modules.setdefault(
    "transformers",
    types.SimpleNamespace(
        AutoModel=object,
        AutoTokenizer=object,
        AutoModelForCausalLM=object,
        LlamaForCausalLM=object,
        LlamaTokenizerFast=object,
    ),
)
sys.modules.setdefault(
    "peft",
    types.SimpleNamespace(PeftModel=object),
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


def test_ticker_level_apply_normalized_volatility_keeps_raw_score():
    ticker = TickerLevelScore(_id="TSLA", ticker="TSLA")
    ticker.weighted_score = 0.8
    ticker.absolute_score = 0.4
    ticker.reliability = 0.5

    ticker.apply_normalized_volatility(0.25)

    assert ticker.weighted_score == 0.8
    assert ticker.raw_weighted_score == 0.8
    assert ticker.normalized_volatility == 0.25
    assert ticker.adjusted_weighted_score == 0.2
    assert ticker.absolute_score == 0.4
    assert ticker.reliability == 0.5


def test_normalized_volatility_lookup_defaults_to_one():
    app = object.__new__(SentimentServiceApp)
    app.normalized_volatility = {"TSLA": 0.6}

    assert app._normalized_volatility_for_ticker("TSLA") == 0.6
    assert app._normalized_volatility_for_ticker("AAPL") == 1.0
    assert app._normalized_volatility_for_ticker("") == 1.0


def test_build_ticker_level_applies_normalized_volatility():
    app = object.__new__(SentimentServiceApp)
    app.normalized_volatility = {"TSLA": 0.5}

    hourly_docs = [
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
            "keywordCounts": {},
            "sourceBreakdown": {"REDDIT": 10},
        }
    ]

    class StubHourlyRepo:
        def find_by_ticker_up_to_hour(self, *, ticker, hour_start_utc, limit_hours):
            return hourly_docs

    app.hourly_repo = StubHourlyRepo()

    ticker_level = app._build_ticker_level(ticker="TSLA", as_of_hour_start_utc=3600)

    assert ticker_level is not None
    assert abs(ticker_level.weighted_score - 0.5) < 1e-9
    assert abs(ticker_level.raw_weighted_score - 0.5) < 1e-9
    assert ticker_level.normalized_volatility == 0.5
    assert abs(ticker_level.adjusted_weighted_score - 0.25) < 1e-9
