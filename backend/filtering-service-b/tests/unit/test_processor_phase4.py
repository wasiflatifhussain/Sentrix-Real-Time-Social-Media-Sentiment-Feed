import math

from filtering_service_b.config.settings import ManipulationSettings
from filtering_service_b.manipulation.repetition_scorer import CrossUserRepetitionScorer
from filtering_service_b.manipulation.simhash import simhash64_unsigned_str
from filtering_service_b.messaging.schemas import CleanedEvent
from filtering_service_b.pipeline.processor import FilterBPhase1Processor
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
        event_id="e-1",
        ticker="TSLA",
        source="reddit",
        entity_type="post",
        created_at_utc=1700000000,
        text_normalized="tesla earnings beat estimates",
        title="Breaking",
        author="user-1",
    )


def _manipulation_settings(**overrides: object) -> ManipulationSettings:
    defaults = {
        "cross_user_enabled": True,
        "cross_user_max_hamming_distance": 0,
        "cross_user_min_matches": 2,
        "cross_user_min_unique_authors": 2,
        "cross_user_penalty": 0.20,
        "cross_user_strong_match_threshold": 4,
        "cross_user_strong_penalty": 0.35,
        "cluster_enabled": True,
        "cluster_min_matches": 3,
        "cluster_min_unique_authors": 3,
        "cluster_max_time_span_seconds": 1800,
        "cluster_penalty": 0.12,
        "cluster_strong_match_threshold": 6,
        "cluster_strong_penalty": 0.22,
        "same_account_enabled": True,
        "same_account_max_hamming_distance": 5,
        "same_account_min_matches": 2,
        "same_account_max_time_span_seconds": 1800,
        "same_account_penalty": 0.18,
        "same_account_strong_match_threshold": 4,
        "same_account_strong_penalty": 0.32,
        "same_account_extreme_match_threshold": 6,
        "same_account_extreme_reject_enabled": False,
        "burst_enabled": True,
        "burst_ratio_threshold": 2.0,
        "burst_amplifier_slope": 0.25,
        "burst_max_multiplier": 1.8,
    }
    defaults.update(overrides)
    return ManipulationSettings(**defaults)


def _keep_relevance() -> RelevanceScore:
    return RelevanceScore(
        decision="KEEP",
        score_delta=0.0,
        similarity=0.70,
        reason_codes=[],
        signals={},
    )


def test_processor_applies_cross_user_repetition_penalty() -> None:
    processor = FilterBPhase1Processor(
        relevance_scorer=StubRelevanceScorer(_keep_relevance()),
        cross_user_scorer=CrossUserRepetitionScorer(settings=_manipulation_settings()),
    )
    current_hash = simhash64_unsigned_str(_event().text_normalized)
    decision = processor.process(
        _event(),
        state_context={
            "tickerSimilarity": [
                {"author": "user-2", "simHash64": current_hash},
                {"author": "user-3", "simHash64": current_hash},
            ]
        },
    )

    assert decision.decision == "KEEP"
    assert decision.credibility_score == 0.8
    assert "CROSS_USER_REPETITION" in decision.decision_reasons


def test_processor_applies_cluster_density_penalty() -> None:
    processor = FilterBPhase1Processor(
        relevance_scorer=StubRelevanceScorer(_keep_relevance()),
        cross_user_scorer=CrossUserRepetitionScorer(settings=_manipulation_settings()),
    )
    current_hash = simhash64_unsigned_str(_event().text_normalized)
    decision = processor.process(
        _event(),
        state_context={
            "tickerSimilarity": [
                {"author": "user-2", "simHash64": current_hash, "timestampUtc": 1000},
                {"author": "user-3", "simHash64": current_hash, "timestampUtc": 1200},
                {"author": "user-4", "simHash64": current_hash, "timestampUtc": 1400},
            ]
        },
    )

    assert decision.decision == "KEEP"
    assert math.isclose(decision.credibility_score, 0.68, abs_tol=1e-9)
    assert "CROSS_USER_REPETITION" in decision.decision_reasons
    assert "DENSE_SIMILARITY_CLUSTER" in decision.decision_reasons


def test_processor_same_account_extreme_reject_override() -> None:
    processor = FilterBPhase1Processor(
        relevance_scorer=StubRelevanceScorer(_keep_relevance()),
        cross_user_scorer=CrossUserRepetitionScorer(
            settings=_manipulation_settings(
                cross_user_min_matches=99,
                cross_user_min_unique_authors=99,
                cross_user_strong_match_threshold=100,
                cluster_min_matches=99,
                cluster_min_unique_authors=99,
                cluster_strong_match_threshold=100,
                same_account_max_hamming_distance=0,
                same_account_extreme_match_threshold=2,
                same_account_extreme_reject_enabled=True,
            )
        ),
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
    assert "SAME_ACCOUNT_REPETITION" in decision.decision_reasons


def test_processor_applies_burst_amplifier_with_repetition_evidence() -> None:
    processor = FilterBPhase1Processor(
        relevance_scorer=StubRelevanceScorer(_keep_relevance()),
        cross_user_scorer=CrossUserRepetitionScorer(
            settings=_manipulation_settings(
                burst_amplifier_slope=0.5, burst_max_multiplier=2.0
            )
        ),
    )
    current_hash = simhash64_unsigned_str(_event().text_normalized)
    decision = processor.process(
        _event(),
        state_context={
            "tickerSimilarity": [
                {"author": "user-2", "simHash64": current_hash},
                {"author": "user-3", "simHash64": current_hash},
            ],
            "burst": {"burstRatio": 3.0},
        },
    )

    assert decision.decision == "KEEP"
    assert math.isclose(decision.credibility_score, 0.7, abs_tol=1e-9)
    assert "BURST_AMPLIFIED_REPETITION" in decision.decision_reasons
    assert decision.signals["stage2BurstAmplified"] is True
    assert math.isclose(decision.signals["stage2BurstExtraPenaltyApplied"], 0.1, abs_tol=1e-9)


def test_processor_does_not_apply_burst_penalty_without_repetition_evidence() -> None:
    processor = FilterBPhase1Processor(
        relevance_scorer=StubRelevanceScorer(_keep_relevance()),
        cross_user_scorer=CrossUserRepetitionScorer(settings=_manipulation_settings()),
    )
    decision = processor.process(
        _event(),
        state_context={
            "tickerSimilarity": [],
            "authorTickerHistory": [],
            "burst": {"burstRatio": 10.0},
        },
    )

    assert decision.decision == "KEEP"
    assert decision.credibility_score == 1.0
    assert "BURST_AMPLIFIED_REPETITION" not in decision.decision_reasons
    assert decision.signals["stage2BurstReason"] == "no_repetition_evidence"


def test_processor_keeps_reason_list_to_top_two_prioritized_reasons() -> None:
    processor = FilterBPhase1Processor(
        relevance_scorer=StubRelevanceScorer(_keep_relevance()),
        cross_user_scorer=CrossUserRepetitionScorer(
            settings=_manipulation_settings(
                cross_user_min_matches=1,
                cross_user_min_unique_authors=1,
                cluster_min_matches=1,
                cluster_min_unique_authors=1,
                same_account_min_matches=1,
                burst_ratio_threshold=1.0,
            )
        ),
    )
    current_hash = simhash64_unsigned_str(_event().text_normalized)
    decision = processor.process(
        _event(),
        state_context={
            "tickerSimilarity": [
                {"author": "user-2", "simHash64": current_hash, "timestampUtc": 1000},
                {"author": "user-3", "simHash64": current_hash, "timestampUtc": 1100},
            ],
            "authorTickerHistory": [
                {"simHash64": current_hash, "timestampUtc": 1000},
            ],
            "burst": {"burstRatio": 3.0},
        },
    )

    assert len(decision.decision_reasons) == 2
    assert decision.decision_reasons == [
        "SAME_ACCOUNT_REPETITION",
        "CROSS_USER_REPETITION",
    ]


def test_processor_has_consistent_stage2_signal_shape_when_stage2_is_unavailable() -> None:
    processor = FilterBPhase1Processor(
        relevance_scorer=StubRelevanceScorer(_keep_relevance()),
        cross_user_scorer=None,
    )

    decision = processor.process(_event(), state_context={})

    assert decision.signals["stage2CrossUserEvaluated"] is False
    assert decision.signals["stage2ClusterEvaluated"] is False
    assert decision.signals["stage2SameAccountEvaluated"] is False
    assert decision.signals["stage2BurstEvaluated"] is False
    assert decision.signals["stage2BurstRatio"] == 0.0
