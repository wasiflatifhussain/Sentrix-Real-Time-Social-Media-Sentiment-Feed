from filtering_service_b.messaging.schemas import CleanedEvent
from filtering_service_b.pipeline.processor import FilterBPhase1Processor
from filtering_service_b.relevance.relevance_scorer import RelevanceScore

class StubRelevanceScorer:
    def __init__(self, response: RelevanceScore) -> None:
        self._response = response
        self.last_event_text: str | None = None
        self.last_ticker: str | None = None

    def score(self, event_text: str, ticker: str) -> RelevanceScore:
        self.last_event_text = event_text
        self.last_ticker = ticker
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


def test_processor_uses_relevance_scorer_and_clamps_high_score() -> None:
    scorer = StubRelevanceScorer(
        RelevanceScore(
            decision="KEEP",
            score_delta=0.02,
            similarity=0.91,
            reason_codes=[],
            signals={"relevanceBand": "strong_relevance", "relevanceSimilarity": 0.91},
        )
    )
    processor = FilterBPhase1Processor(relevance_scorer=scorer)

    decision = processor.process(_event(), state_context={"ignored": True})

    assert decision.decision == "KEEP"
    assert decision.credibility_score == 1.0
    assert decision.decision_reasons == []
    assert scorer.last_ticker == "TSLA"
    assert scorer.last_event_text == "Breaking tesla earnings beat estimates"


def test_processor_rejects_with_reason_and_envelope_signals() -> None:
    scorer = StubRelevanceScorer(
        RelevanceScore(
            decision="REJECT",
            score_delta=-1.0,
            similarity=0.12,
            reason_codes=["EXTREME_LOW_TICKER_RELEVANCE"],
            signals={
                "relevanceBand": "extreme_low_relevance",
                "relevanceSimilarity": 0.12,
                "tickerProfileFound": True,
            },
        )
    )
    processor = FilterBPhase1Processor(relevance_scorer=scorer)

    decision = processor.process(_event())
    out = processor.build_output_envelope(
        {"ingestorEvent": {"eventId": "e-1"}},
        decision,
        state_signals={"tickerSimilarityCount": 3},
    )

    assert decision.decision == "REJECT"
    assert decision.credibility_score == 0.0
    assert decision.decision_reasons == ["EXTREME_LOW_TICKER_RELEVANCE"]
    assert out["filterMeta"]["filterReason"] == "EXTREME_LOW_TICKER_RELEVANCE"
    assert out["filterMeta"]["signals"]["stage"] == "phase1_ticker_relevance"
    assert out["filterMeta"]["signals"]["relevanceBand"] == "extreme_low_relevance"
    assert out["filterMeta"]["signals"]["tickerSimilarityCount"] == 3


def test_processor_does_not_duplicate_title_if_already_in_text_normalized() -> None:
    scorer = StubRelevanceScorer(
        RelevanceScore(
            decision="KEEP",
            score_delta=0.0,
            similarity=0.70,
            reason_codes=[],
            signals={},
        )
    )
    processor = FilterBPhase1Processor(relevance_scorer=scorer)
    event = CleanedEvent(
        event_id="e-2",
        ticker="TSLA",
        source="REDDIT",
        entity_type="POST",
        created_at_utc=1774553281,
        text_normalized="Three straight wins got me feeling like the future’s looking bright\nBody text",
        title="Three straight wins got me feeling like the future’s looking bright",
        author="Simple-Dimension8684",
    )

    _ = processor.process(event)

    assert (
        scorer.last_event_text
        == "Three straight wins got me feeling like the future’s looking bright\nBody text"
    )
