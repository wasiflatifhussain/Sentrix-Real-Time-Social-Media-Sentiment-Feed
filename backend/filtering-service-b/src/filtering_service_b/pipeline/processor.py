from __future__ import annotations

import copy
import time
from dataclasses import dataclass

from filtering_service_b.messaging.schemas import CleanedEvent


@dataclass(frozen=True)
class FilterDecision:
    decision: str
    credibility_score: float
    decision_reasons: list[str]


class FilterBPhase1Processor:
    """
    Phase 1 processor:
    - Reads Filter A cleaned envelope
    - Produces Filter B filtered/rejected envelope
    - Uses simple pass-through KEEP policy for valid events
    """

    def process(self, event: CleanedEvent) -> FilterDecision:
        # Phase 1 keeps valid records and establishes the scoring contract.
        _ = event
        return FilterDecision(
            decision="KEEP",
            credibility_score=1.0,
            decision_reasons=[],
        )

    @staticmethod
    def build_output_envelope(
        original_payload: dict,
        decision: FilterDecision,
        filter_reason: str | None = None,
    ) -> dict:
        now_utc = int(time.time())
        out = copy.deepcopy(original_payload)

        reason = filter_reason
        if reason is None and decision.decision_reasons:
            reason = decision.decision_reasons[0]

        out["filterMeta"] = {
            "filterStage": "semantic_gate_B",
            "decision": decision.decision,
            "filterReason": reason,
            "decisionReasons": decision.decision_reasons,
            "credibilityScore": float(decision.credibility_score),
            "processedAtUtc": now_utc,
            "tags": None,
            "signals": {
                "credibilityScore": float(decision.credibility_score),
                "stage": "phase1_kafka_io",
            },
        }

        return out
