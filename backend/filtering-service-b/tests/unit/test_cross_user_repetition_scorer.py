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
