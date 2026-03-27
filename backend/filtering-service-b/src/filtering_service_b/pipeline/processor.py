from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, field

from filtering_service_b.manipulation.simhash import simhash64_unsigned_str
from filtering_service_b.messaging.schemas import CleanedEvent
from filtering_service_b.relevance.relevance_scorer import TickerRelevanceScorer

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FilterDecision:
    decision: str
    credibility_score: float
    decision_reasons: list[str]
    signals: dict[str, object] = field(default_factory=dict)


class FilterBPhase1Processor:
    """
    Phase 1 processor:
    - Reads Filter A cleaned envelope
    - Produces Filter B filtered/rejected envelope
    - Uses simple pass-through KEEP policy for valid events
    """

    def __init__(self, relevance_scorer: TickerRelevanceScorer) -> None:
        self._relevance_scorer = relevance_scorer

    def process(
        self, event: CleanedEvent, state_context: dict | None = None
    ) -> FilterDecision:
        _ = state_context
        event_text = _build_event_text(event)
        relevance = self._relevance_scorer.score(
            event_text=event_text, ticker=event.ticker
        )
        score = _clamp_score(1.0 + relevance.score_delta)
        stage2_signals = _build_stage2_foundation_signals(event)
        merged_signals = dict(relevance.signals)
        merged_signals.update(stage2_signals)

        return FilterDecision(
            decision=relevance.decision,
            credibility_score=score,
            decision_reasons=relevance.reason_codes,
            signals=merged_signals,
        )

    @staticmethod
    def build_output_envelope(
        original_payload: dict,
        decision: FilterDecision,
        filter_reason: str | None = None,
        state_signals: dict | None = None,
    ) -> dict:
        now_utc = int(time.time())
        out = copy.deepcopy(original_payload)

        reason = filter_reason
        if reason is None and decision.decision_reasons:
            reason = decision.decision_reasons[0]

        signals = {
            "credibilityScore": float(decision.credibility_score),
            "stage": "phase1_ticker_relevance",
        }
        signals.update(decision.signals)
        if state_signals:
            signals.update(state_signals)

        out["filterMeta"] = {
            "filterStage": "semantic_gate_B",
            "decision": decision.decision,
            "filterReason": reason,
            "decisionReasons": decision.decision_reasons,
            "credibilityScore": float(decision.credibility_score),
            "processedAtUtc": now_utc,
            "tags": None,
            "signals": signals,
        }

        return out


def _build_event_text(event: CleanedEvent) -> str:
    text = event.text_normalized.strip()
    if event.title and event.title.strip():
        title = event.title.strip()
        if text.lower().startswith(title.lower()):
            return text
        return f"{title} {text}"
    return text


def _clamp_score(score: float) -> float:
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return float(score)


def _build_stage2_foundation_signals(event: CleanedEvent) -> dict[str, object]:
    try:
        return {
            "stage2SimHashReady": True,
            "stage2SimHash": simhash64_unsigned_str(event.text_normalized),
        }
    except Exception:
        log.exception("Failed generating stage2 SimHash eventId=%s", event.event_id)
        return {"stage2SimHashReady": False}
