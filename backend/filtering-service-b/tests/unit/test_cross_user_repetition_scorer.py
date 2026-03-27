from filtering_service_b.config.settings import ManipulationSettings
from filtering_service_b.manipulation.repetition_scorer import (
    REASON_CROSS_USER_REPETITION,
    CrossUserRepetitionScorer,
)


def _settings() -> ManipulationSettings:
    return ManipulationSettings(
        cross_user_enabled=True,
        cross_user_max_hamming_distance=1,
        cross_user_min_matches=2,
        cross_user_min_unique_authors=2,
        cross_user_penalty=0.20,
        cross_user_strong_match_threshold=4,
        cross_user_strong_penalty=0.35,
        cluster_enabled=True,
        cluster_min_matches=3,
        cluster_min_unique_authors=3,
        cluster_max_time_span_seconds=1800,
        cluster_penalty=0.12,
        cluster_strong_match_threshold=6,
        cluster_strong_penalty=0.22,
        same_account_enabled=True,
        same_account_max_hamming_distance=5,
        same_account_min_matches=2,
        same_account_max_time_span_seconds=1800,
        same_account_penalty=0.18,
        same_account_strong_match_threshold=4,
        same_account_strong_penalty=0.32,
        same_account_extreme_match_threshold=6,
        same_account_extreme_reject_enabled=False,
    )


def test_no_penalty_when_not_enough_cross_user_matches() -> None:
    scorer = CrossUserRepetitionScorer(settings=_settings())
    result = scorer.score(
        current_simhash=15,
        current_author="alice",
        ticker_similarity_history=[
            {"author": "bob", "simHash64": 15},
        ],
    )

    assert result.score_delta == 0.0
    assert result.reason_codes == []
    assert result.signals["stage2CrossUserTriggered"] is False


def test_penalty_when_multiple_similar_posts_from_multiple_authors() -> None:
    scorer = CrossUserRepetitionScorer(settings=_settings())
    result = scorer.score(
        current_simhash=15,
        current_author="alice",
        ticker_similarity_history=[
            {"author": "bob", "simHash64": 15},
            {"author": "charlie", "simHash64": 14},  # hamming distance = 1
        ],
    )

    assert result.score_delta == -0.20
    assert result.reason_codes == [REASON_CROSS_USER_REPETITION]
    assert result.signals["stage2CrossUserMatchCount"] == 2
    assert result.signals["stage2CrossUserUniqueAuthorCount"] == 2


def test_same_author_matches_do_not_trigger_cross_user_penalty() -> None:
    scorer = CrossUserRepetitionScorer(settings=_settings())
    result = scorer.score(
        current_simhash=15,
        current_author="alice",
        ticker_similarity_history=[
            {"author": "alice", "simHash64": 15},
            {"author": "alice", "simHash64": 14},
            {"author": "alice", "simHash64": 13},
        ],
    )

    assert result.score_delta == 0.0
    assert result.reason_codes == []
    assert result.signals["stage2CrossUserUniqueAuthorCount"] == 0


def test_cluster_density_adds_penalty_when_dense_and_time_compact() -> None:
    scorer = CrossUserRepetitionScorer(settings=_settings())
    result = scorer.score(
        current_simhash=15,
        current_author="alice",
        ticker_similarity_history=[
            {"author": "bob", "simHash64": 15, "timestampUtc": 1000},
            {"author": "charlie", "simHash64": 14, "timestampUtc": 1200},
            {"author": "david", "simHash64": 15, "timestampUtc": 1400},
        ],
    )

    assert result.score_delta == -(0.20 + 0.12)
    assert "CROSS_USER_REPETITION" in result.reason_codes
    assert "DENSE_SIMILARITY_CLUSTER" in result.reason_codes
    assert result.signals["stage2ClusterTriggered"] is True
    assert result.signals["stage2ClusterTimeSpanSeconds"] == 400


def test_same_account_penalty_and_optional_extreme_reject() -> None:
    settings = _settings()
    scorer = CrossUserRepetitionScorer(settings=settings)
    result = scorer.score_same_account(
        current_simhash=15,
        author_ticker_history=[
            {"simHash64": 15, "timestampUtc": 1000},
            {"simHash64": 15, "timestampUtc": 1100},
        ],
    )
    assert result.score_delta == -0.18
    assert result.reason_codes == ["SAME_ACCOUNT_REPETITION"]
    assert result.force_reject is False

    scorer_reject = CrossUserRepetitionScorer(
        settings=ManipulationSettings(
            **{
                **settings.__dict__,
                "same_account_extreme_reject_enabled": True,
                "same_account_extreme_match_threshold": 2,
            }
        )
    )
    reject_result = scorer_reject.score_same_account(
        current_simhash=15,
        author_ticker_history=[
            {"simHash64": 15, "timestampUtc": 1000},
            {"simHash64": 15, "timestampUtc": 1100},
        ],
    )
    assert reject_result.force_reject is True
