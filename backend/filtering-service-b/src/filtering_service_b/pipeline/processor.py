from __future__ import annotations

import copy
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from filtering_service_b.manipulation.repetition_scorer import (
    CrossUserRepetitionScore,
    CrossUserRepetitionScorer,
    SameAccountRepetitionScore,
)
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

    def __init__(
        self,
        relevance_scorer: TickerRelevanceScorer,
        cross_user_scorer: CrossUserRepetitionScorer | None = None,
    ) -> None:
        self._relevance_scorer = relevance_scorer
        self._cross_user_scorer = cross_user_scorer

    def process(
        self, event: CleanedEvent, state_context: dict | None = None
    ) -> FilterDecision:
        _ = state_context
        event_text = _build_event_text(event)
        relevance = self._relevance_scorer.score(
            event_text=event_text, ticker=event.ticker
        )
        stage2_signals = _build_stage2_foundation_signals(event)
        repetition = _score_cross_user_repetition(
            cross_user_scorer=self._cross_user_scorer,
            event=event,
            stage2_signals=stage2_signals,
            state_context=state_context,
            relevance_decision=relevance.decision,
        )
        same_account = _score_same_account_repetition(
            cross_user_scorer=self._cross_user_scorer,
            stage2_signals=stage2_signals,
            state_context=state_context,
            relevance_decision=relevance.decision,
        )
        score = _clamp_score(
            1.0 + relevance.score_delta + repetition.score_delta + same_account.score_delta
        )

        merged_signals = dict(relevance.signals)
        merged_signals.update(stage2_signals)
        merged_signals.update(repetition.signals)
        merged_signals.update(same_account.signals)

        reasons: list[str] = []
        reasons.extend(relevance.reason_codes)
        for reason in repetition.reason_codes:
            if reason not in reasons:
                reasons.append(reason)
        for reason in same_account.reason_codes:
            if reason not in reasons:
                reasons.append(reason)
        reasons = reasons[:2]

        decision_value = relevance.decision
        if same_account.force_reject:
            decision_value = "REJECT"
            score = 0.0

        return FilterDecision(
            decision=decision_value,
            credibility_score=score,
            decision_reasons=reasons,
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


def _score_cross_user_repetition(
    cross_user_scorer: CrossUserRepetitionScorer | None,
    event: CleanedEvent,
    stage2_signals: dict[str, object],
    state_context: dict[str, Any] | None,
    relevance_decision: str,
) -> CrossUserRepetitionScore:
    if cross_user_scorer is None:
        return CrossUserRepetitionScore(
            score_delta=0.0,
            reason_codes=[],
            signals={"stage2CrossUserEvaluated": False, "stage2CrossUserEnabled": False},
        )

    if relevance_decision != "KEEP":
        return CrossUserRepetitionScore(
            score_delta=0.0,
            reason_codes=[],
            signals={
                "stage2CrossUserEvaluated": False,
                "stage2CrossUserEnabled": True,
                "stage2CrossUserReason": "skipped_relevance_reject",
            },
        )

    current_simhash = _safe_int(stage2_signals.get("stage2SimHash"))
    ticker_similarity_history = (state_context or {}).get("tickerSimilarity", [])
    if not isinstance(ticker_similarity_history, list):
        ticker_similarity_history = []

    return cross_user_scorer.score(
        current_simhash=current_simhash,
        current_author=event.author,
        ticker_similarity_history=ticker_similarity_history,
    )


def _score_same_account_repetition(
    cross_user_scorer: CrossUserRepetitionScorer | None,
    stage2_signals: dict[str, object],
    state_context: dict[str, Any] | None,
    relevance_decision: str,
) -> SameAccountRepetitionScore:
    if cross_user_scorer is None:
        return SameAccountRepetitionScore(
            score_delta=0.0,
            reason_codes=[],
            signals={"stage2SameAccountEvaluated": False, "stage2SameAccountEnabled": False},
            force_reject=False,
        )

    if relevance_decision != "KEEP":
        return SameAccountRepetitionScore(
            score_delta=0.0,
            reason_codes=[],
            signals={
                "stage2SameAccountEvaluated": False,
                "stage2SameAccountEnabled": True,
                "stage2SameAccountReason": "skipped_relevance_reject",
            },
            force_reject=False,
        )

    current_simhash = _safe_int(stage2_signals.get("stage2SimHash"))
    author_ticker_history = (state_context or {}).get("authorTickerHistory", [])
    if not isinstance(author_ticker_history, list):
        author_ticker_history = []

    return cross_user_scorer.score_same_account(
        current_simhash=current_simhash,
        author_ticker_history=author_ticker_history,
    )


def _safe_int(value: object) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None
