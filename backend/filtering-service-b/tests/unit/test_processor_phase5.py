from filtering_service_b.messaging.schemas import CleanedEvent
from filtering_service_b.novelty.novelty_scorer import NoveltyScore
from filtering_service_b.pipeline.processor import FilterBSemanticProcessor
from filtering_service_b.relevance.relevance_scorer import RelevanceScore


class StubRelevanceScorer:
    def __init__(self, response: RelevanceScore) -> None:
        self._response = response

    def score(self, event_text: str, ticker: str) -> RelevanceScore:
        _ = event_text
        _ = ticker
        return self._response


class StubNoveltyScorer:
    def __init__(self, response: NoveltyScore) -> None:
        self._response = response
        self.last_event_text: str | None = None
        self.last_refs: list[dict] | None = None

    def score(self, event_text: str, accepted_references: list[dict] | None) -> NoveltyScore:
        self.last_event_text = event_text
        self.last_refs = accepted_references
        return self._response


def _event() -> CleanedEvent:
    return CleanedEvent(
        event_id="e-phase5",
        ticker="TSLA",
        source="REDDIT",
        entity_type="POST",
        created_at_utc=1774553281,
        text_normalized="tesla earnings outlook improved",
        title="TSLA update",
        author="u-1",
    )


def test_processor_applies_novelty_penalty_when_enabled() -> None:
    novelty = StubNoveltyScorer(
        NoveltyScore(
            score_delta=-0.20,
            reason_codes=["LOW_NOVELTY"],
            signals={"stage3NoveltyEvaluated": True, "stage3NoveltyBand": "low_novelty"},
        )
    )
    processor = FilterBSemanticProcessor(
        relevance_scorer=StubRelevanceScorer(
            RelevanceScore(
                decision="KEEP",
                score_delta=0.0,
                similarity=0.70,
                reason_codes=[],
                signals={},
            )
        ),
        novelty_scorer=novelty,
    )
    decision = processor.process(
        _event(),
        state_context={"acceptedNovelty": [{"text": "older reference"}]},
    )
    assert decision.decision == "KEEP"
    assert decision.credibility_score == 0.8
    assert "LOW_NOVELTY" in decision.decision_reasons
    assert novelty.last_refs == [{"text": "older reference"}]


def test_processor_skips_novelty_when_relevance_rejects() -> None:
    novelty = StubNoveltyScorer(
        NoveltyScore(
            score_delta=-0.20,
            reason_codes=["LOW_NOVELTY"],
            signals={"stage3NoveltyEvaluated": True},
        )
    )
    processor = FilterBSemanticProcessor(
        relevance_scorer=StubRelevanceScorer(
            RelevanceScore(
                decision="REJECT",
                score_delta=-1.0,
                similarity=0.10,
                reason_codes=["EXTREME_LOW_TICKER_RELEVANCE"],
                signals={},
            )
        ),
        novelty_scorer=novelty,
    )
    decision = processor.process(_event(), state_context={"acceptedNovelty": [{"text": "x"}]})
    assert decision.decision == "REJECT"
    assert decision.credibility_score == 0.0
    assert decision.signals["stage3NoveltyReason"] == "skipped_relevance_reject"
