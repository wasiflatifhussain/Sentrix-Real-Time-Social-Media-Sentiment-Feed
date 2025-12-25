from sentiment_service.domain.models import CleanedEvent
from sentiment_service.domain.scoring import StubSentimentScorer


def test_stub_scorer_is_deterministic():
    e = CleanedEvent(
        event_id="reddit:t3_phase6_wave_01",
        ticker="TSLA",
        source="REDDIT",
        entity_type="POST",
        created_at_utc=1766567348,
        text_normalized="Watching TSLA into the next session. Price is holding above support.",
    )

    scorer = StubSentimentScorer(max_keywords=5)
    r1 = scorer.score(e)
    r2 = scorer.score(e)

    assert r1.score == r2.score
    assert r1.confidence == r2.confidence
    assert r1.keywords == r2.keywords
    assert -1.0 <= r1.score <= 1.0
    assert 0.0 <= (r1.confidence or 0.0) <= 1.0
    assert len(r1.keywords) <= 5
