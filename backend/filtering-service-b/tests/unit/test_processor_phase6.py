import math

from filtering_service_b.config.settings import ManipulationSettings
from filtering_service_b.manipulation.repetition_scorer import CrossUserRepetitionScorer
from filtering_service_b.manipulation.simhash import simhash64_unsigned_str
from filtering_service_b.messaging.schemas import CleanedEvent
from filtering_service_b.pipeline.processor import FilterBSemanticProcessor
from filtering_service_b.relevance.relevance_scorer import RelevanceScore


class StubRelevanceScorer:
    def __init__(self, response: RelevanceScore) -> None:
        self._response = response

    def score(self, event_text: str, ticker: str) -> RelevanceScore:
        _ = event_text
        _ = ticker
        return self._response


def _event() -> CleanedEvent:
    return CleanedEvent(
        event_id="e-phase6",
        ticker="TSLA",
        source="REDDIT",
        entity_type="POST",
        created_at_utc=1774553281,
        text_normalized="tesla earnings outlook improved",
        title="TSLA update",
        author="u-1",
    )


def _keep_relevance(score_delta: float) -> RelevanceScore:
    return RelevanceScore(
        decision="KEEP",
        score_delta=score_delta,
        similarity=0.70,
        reason_codes=[],
        signals={},
    )


def _same_account_force_reject_scorer() -> CrossUserRepetitionScorer:
    settings = ManipulationSettings(
        cross_user_enabled=True,
        cross_user_max_hamming_distance=0,
        cross_user_min_matches=99,
        cross_user_min_unique_authors=99,
        cross_user_penalty=0.20,
        cross_user_strong_match_threshold=100,
        cross_user_strong_penalty=0.35,
        cluster_enabled=True,
        cluster_min_matches=99,
        cluster_min_unique_authors=99,
        cluster_max_time_span_seconds=1800,
        cluster_penalty=0.12,
        cluster_strong_match_threshold=100,
        cluster_strong_penalty=0.22,
        same_account_enabled=True,
        same_account_max_hamming_distance=0,
        same_account_min_matches=2,
        same_account_max_time_span_seconds=1800,
        same_account_penalty=0.18,
        same_account_strong_match_threshold=4,
        same_account_strong_penalty=0.32,
        same_account_extreme_match_threshold=2,
        same_account_extreme_reject_enabled=True,
        burst_enabled=True,
        burst_ratio_threshold=2.0,
        burst_amplifier_slope=0.25,
        burst_max_multiplier=1.8,
    )
    return CrossUserRepetitionScorer(settings=settings)


def test_threshold_rejects_when_score_is_below_0_40() -> None:
    processor = FilterBSemanticProcessor(
        relevance_scorer=StubRelevanceScorer(_keep_relevance(score_delta=-0.61)),
        final_keep_threshold=0.40,
    )
    decision = processor.process(_event(), state_context={})
    assert decision.decision == "REJECT"
    assert decision.credibility_score == 0.0
    assert decision.signals["finalDecisionMode"] == "threshold_reject"
    assert math.isclose(decision.signals["finalScoreBeforeDecision"], 0.39, abs_tol=1e-9)
    assert math.isclose(decision.signals["finalThresholdUsed"], 0.40, abs_tol=1e-9)


def test_threshold_keeps_when_score_equals_0_40() -> None:
    processor = FilterBSemanticProcessor(
        relevance_scorer=StubRelevanceScorer(_keep_relevance(score_delta=-0.60)),
        final_keep_threshold=0.40,
    )
    decision = processor.process(_event(), state_context={})
    assert decision.decision == "KEEP"
    assert math.isclose(decision.credibility_score, 0.40, abs_tol=1e-9)
    assert decision.signals["finalDecisionMode"] == "threshold_keep"


def test_threshold_keeps_when_score_is_above_0_40() -> None:
    processor = FilterBSemanticProcessor(
        relevance_scorer=StubRelevanceScorer(_keep_relevance(score_delta=-0.59)),
        final_keep_threshold=0.40,
    )
    decision = processor.process(_event(), state_context={})
    assert decision.decision == "KEEP"
    assert math.isclose(decision.credibility_score, 0.41, abs_tol=1e-9)
    assert decision.signals["finalDecisionMode"] == "threshold_keep"


def test_relevance_reject_override_takes_precedence_over_threshold() -> None:
    processor = FilterBSemanticProcessor(
        relevance_scorer=StubRelevanceScorer(
            RelevanceScore(
                decision="REJECT",
                score_delta=0.0,
                similarity=0.10,
                reason_codes=["EXTREME_LOW_TICKER_RELEVANCE"],
                signals={},
            )
        ),
        final_keep_threshold=0.40,
    )
    decision = processor.process(_event(), state_context={})
    assert decision.decision == "REJECT"
    assert decision.credibility_score == 0.0
    assert decision.signals["finalDecisionMode"] == "override_relevance_reject"


def test_same_account_extreme_override_takes_precedence_over_threshold() -> None:
    processor = FilterBSemanticProcessor(
        relevance_scorer=StubRelevanceScorer(_keep_relevance(score_delta=0.0)),
        cross_user_scorer=_same_account_force_reject_scorer(),
        final_keep_threshold=0.40,
    )
    current_hash = simhash64_unsigned_str(_event().text_normalized)
    decision = processor.process(
        _event(),
        state_context={
            "authorTickerHistory": [
                {"simHash64": current_hash, "timestampUtc": 1000},
                {"simHash64": current_hash, "timestampUtc": 1100},
            ],
            "tickerSimilarity": [],
        },
    )
    assert decision.decision == "REJECT"
    assert decision.credibility_score == 0.0
    assert decision.signals["finalDecisionMode"] == "override_same_account_extreme"
