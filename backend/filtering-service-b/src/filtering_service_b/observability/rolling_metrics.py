from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from math import ceil

from filtering_service_b.pipeline.processor import FilterDecision

log = logging.getLogger(__name__)


@dataclass
class RollingMetricsLogger:
    summary_every: int
    final_threshold: float
    near_threshold_window: float = 0.05
    _window_processed: int = 0
    _window_keep: int = 0
    _window_reject: int = 0
    _window_invalid_input: int = 0
    _window_reason_counts: Counter[str] = field(default_factory=Counter)
    _window_latencies_ms: list[float] = field(default_factory=list)
    _window_scores: list[float] = field(default_factory=list)
    _window_near_threshold: int = 0
    _total_processed: int = 0

    def record(self, decision: FilterDecision, latency_ms: float, invalid_input: bool = False) -> None:
        self._window_processed += 1
        self._total_processed += 1

        if decision.decision == "KEEP":
            self._window_keep += 1
        elif decision.decision == "REJECT":
            self._window_reject += 1

        if invalid_input:
            self._window_invalid_input += 1

        self._window_latencies_ms.append(latency_ms)
        self._window_scores.append(decision.credibility_score)

        if abs(decision.credibility_score - self.final_threshold) <= self.near_threshold_window:
            self._window_near_threshold += 1

        for reason in decision.decision_reasons:
            self._window_reason_counts[reason] += 1

        if self._window_processed >= self.summary_every:
            self.emit_summary()
            self._reset_window()

    def emit_summary(self) -> None:
        processed = self._window_processed
        if processed == 0:
            return

        reject_rate = (self._window_reject / processed) * 100.0
        near_threshold_rate = (self._window_near_threshold / processed) * 100.0
        avg_latency = sum(self._window_latencies_ms) / processed
        p95_latency = _p95(self._window_latencies_ms)
        avg_score = sum(self._window_scores) / processed
        top_reasons = ", ".join(
            f"{reason}:{count}" for reason, count in self._window_reason_counts.most_common(5)
        )
        if not top_reasons:
            top_reasons = "none"

        log.info(
            (
                "RollingSummary window=%s total=%s keep=%s reject=%s rejectRate=%.2f%% "
                "invalidInput=%s avgLatencyMs=%.2f p95LatencyMs=%.2f avgScore=%.3f "
                "nearThresholdPct=%.2f%% threshold=%.3f topReasons=[%s]"
            ),
            processed,
            self._total_processed,
            self._window_keep,
            self._window_reject,
            reject_rate,
            self._window_invalid_input,
            avg_latency,
            p95_latency,
            avg_score,
            near_threshold_rate,
            self.final_threshold,
            top_reasons,
        )

    def flush(self) -> None:
        self.emit_summary()
        self._reset_window()

    def _reset_window(self) -> None:
        self._window_processed = 0
        self._window_keep = 0
        self._window_reject = 0
        self._window_invalid_input = 0
        self._window_reason_counts.clear()
        self._window_latencies_ms.clear()
        self._window_scores.clear()
        self._window_near_threshold = 0


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, ceil(len(ordered) * 0.95) - 1))
    return ordered[idx]
