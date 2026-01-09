# hourly_aggregation.py
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional

from event_scoring import clamp


@dataclass
class EventContribution:
    score: float            # eventScore in [-1, +1]
    weight: float = 1.0     # engagement/credibility weight
    confidence: float = 0.0 # eventConfidence in [0, 1]


@dataclass
class HourAgg:
    # core aggregates
    score_sum: float              # Σ s_i
    count: int                    # N
    hour_avg: float               # clamp(Σ s_i / N)
    w_vol: float                  # min(1, N / C)
    # weighted aggregates
    weighted_score_sum: float = 0.0   # Σ (s_i * w_i)
    weighted_hour_avg: float = 0.0   # clamp(Σ s_i w_i / Σ w_i)
    weight_sum: float = 0.0          # Σ w_i
    # confidence diagnostics
    avg_confidence: float = 0.0      # Σ c_i / N
    weighted_confidence: float = 0.0 # Σ c_i w_i / Σ w_i
    hour_confidence: float = 0.0     # weighted_confidence * w_vol
    # robustness diagnostics
    clipped_count: int = 0
    min_score: float = 0.0
    max_score: float = 0.0
    effective_n: float = 0.0         # (Σ w_i)^2 / Σ w_i^2


HOUR_RISK_PROFILES = {
    "conservative": {
        "clip": 1.0,
        "weight_power": 0.6,
        "conf_power": 1.3,
        "conf_eps": 0.05,
        "volume_cap": 80.0,
    },
    "moderate": {
        "clip": 1.0,
        "weight_power": 0.8,
        "conf_power": 1.0,
        "conf_eps": 0.05,
        "volume_cap": 50.0,
    },
    "aggressive": {
        "clip": 1.0,
        "weight_power": 1.0,
        "conf_power": 0.8,
        "conf_eps": 0.03,
        "volume_cap": 30.0,
    },
}


def aggregate_hour(weighted_sents: List[float], C: int = 50) -> HourAgg:
    """
    Backwards-compatible aggregation.
    Treat each element as an eventScore with unit weight/confidence.
    """
    events = [EventContribution(score=s, weight=1.0, confidence=1.0) for s in weighted_sents]
    return aggregate_hour_weighted(events, C=C, profile="moderate")


def aggregate_hour_weighted(
    events: Iterable[EventContribution],
    C: int = 50,
    profile: str = "moderate",
) -> HourAgg:
    """
    Weighted hourly aggregation with discrete-math-friendly formulas:
      scoreSum = Σ s_i
      weightedScoreSum = Σ (s_i * w_i)
      hourAvg = clamp(scoreSum / N)
      weightedHourAvg = clamp(weightedScoreSum / Σ w_i)
      w_vol = min(1, N / C)
      effective_n = (Σ w_i)^2 / Σ w_i^2
    """
    params = HOUR_RISK_PROFILES.get(profile, HOUR_RISK_PROFILES["moderate"])
    clip = float(params["clip"])
    w_pow = float(params["weight_power"])
    c_pow = float(params["conf_power"])
    c_eps = float(params["conf_eps"])

    C_eff = float(C) if isinstance(C, (int, float)) and C > 0 else float(params["volume_cap"])
    C_eff = max(1.0, C_eff)

    score_sum = 0.0
    weighted_score_sum = 0.0
    weight_sum = 0.0
    weight_sq_sum = 0.0
    conf_sum = 0.0
    conf_weighted_sum = 0.0
    clipped_count = 0
    count = 0
    min_score: Optional[float] = None
    max_score: Optional[float] = None

    for e in events:
        raw_score = float(e.score)
        score = clamp(raw_score, -clip, clip)
        if score != raw_score:
            clipped_count += 1

        w_raw = max(0.0, float(e.weight))
        conf = clamp(float(e.confidence), 0.0, 1.0)
        w_eff = (w_raw ** w_pow) * ((conf + c_eps) ** c_pow)

        score_sum += score
        weighted_score_sum += score * w_eff
        weight_sum += w_eff
        weight_sq_sum += w_eff * w_eff
        conf_sum += conf
        conf_weighted_sum += conf * w_eff
        count += 1

        min_score = score if min_score is None else min(min_score, score)
        max_score = score if max_score is None else max(max_score, score)

    if count == 0:
        return HourAgg(
            score_sum=0.0,
            count=0,
            hour_avg=0.0,
            w_vol=0.0,
        )

    hour_avg = clamp(score_sum / float(count), -1.0, 1.0)
    weighted_hour_avg = 0.0 if weight_sum <= 0 else clamp(weighted_score_sum / weight_sum, -1.0, 1.0)
    w_vol = min(1.0, float(count) / C_eff)
    avg_conf = conf_sum / float(count)
    weighted_conf = 0.0 if weight_sum <= 0 else (conf_weighted_sum / weight_sum)
    hour_conf = clamp(weighted_conf * w_vol, 0.0, 1.0)
    effective_n = 0.0 if weight_sq_sum <= 0 else ((weight_sum * weight_sum) / weight_sq_sum)

    return HourAgg(
        score_sum=score_sum,
        count=count,
        hour_avg=hour_avg,
        w_vol=w_vol,
        weighted_score_sum=weighted_score_sum,
        weighted_hour_avg=weighted_hour_avg,
        weight_sum=weight_sum,
        avg_confidence=avg_conf,
        weighted_confidence=weighted_conf,
        hour_confidence=hour_conf,
        clipped_count=clipped_count,
        min_score=0.0 if min_score is None else min_score,
        max_score=0.0 if max_score is None else max_score,
        effective_n=effective_n,
    )


def aggregate_from_scores_weights(
    scores: List[float],
    weights: Optional[List[float]] = None,
    confidences: Optional[List[float]] = None,
    C: int = 50,
    profile: str = "moderate",
) -> HourAgg:
    """
    Convenience helper for arrays:
      score_i ∈ [-1, +1], weight_i ≥ 0, confidence_i ∈ [0, 1]
    """
    weights = weights or [1.0 for _ in scores]
    confidences = confidences or [1.0 for _ in scores]
    events = [
        EventContribution(score=s, weight=w, confidence=c)
        for s, w, c in zip(scores, weights, confidences)
    ]
    return aggregate_hour_weighted(events, C=C, profile=profile)




@@ -1,29 +1,176 @@
 # hourly_aggregation.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional

from event_scoring import clamp


@dataclass
class EventContribution:
    score: float            # eventScore in [-1, +1]
    weight: float = 1.0     # engagement/credibility weight
    confidence: float = 0.0 # eventConfidence in [0, 1]


@dataclass
class HourAgg:
    score_sum: float     # Σ weightedSent_e
    count: int           # number of events
    hour_avg: float      # score_sum / count (clamped)
    w_vol: float         # min(1, count / C)
    # core aggregates
    score_sum: float              # Σ s_i
    count: int                    # N
    hour_avg: float               # clamp(Σ s_i / N)
    w_vol: float                  # min(1, N / C)
    # weighted aggregates
    weighted_score_sum: float = 0.0   # Σ (s_i * w_i)
    weighted_hour_avg: float = 0.0   # clamp(Σ s_i w_i / Σ w_i)
    weight_sum: float = 0.0          # Σ w_i
    # confidence diagnostics
    avg_confidence: float = 0.0      # Σ c_i / N
    weighted_confidence: float = 0.0 # Σ c_i w_i / Σ w_i
    hour_confidence: float = 0.0     # weighted_confidence * w_vol
    # robustness diagnostics
    clipped_count: int = 0
    min_score: float = 0.0
    max_score: float = 0.0
    effective_n: float = 0.0         # (Σ w_i)^2 / Σ w_i^2


HOUR_RISK_PROFILES = {
    "conservative": {
        "clip": 1.0,
        "weight_power": 0.6,
        "conf_power": 1.3,
        "conf_eps": 0.05,
        "volume_cap": 80.0,
    },
    "moderate": {
        "clip": 1.0,
        "weight_power": 0.8,
        "conf_power": 1.0,
        "conf_eps": 0.05,
        "volume_cap": 50.0,
    },
    "aggressive": {
        "clip": 1.0,
        "weight_power": 1.0,
        "conf_power": 0.8,
        "conf_eps": 0.03,
        "volume_cap": 30.0,
    },
}


def aggregate_hour(weighted_sents: List[float], C: int = 50) -> HourAgg:
    """
    scoreSum = Σ weightedSent_e
    count = N
    hourAvg = scoreSum / count (clamp to [-1, +1])
    w_vol = min(1, count / C)
    Backwards-compatible aggregation.
    Treat each element as an eventScore with unit weight/confidence.
    """
    count = len(weighted_sents)
    score_sum = float(sum(weighted_sents))
    if count == 0:
        return HourAgg(score_sum=0.0, count=0, hour_avg=0.0, w_vol=0.0)

    hour_avg = clamp(score_sum / count, -1.0, 1.0)
    w_vol = min(1.0, count / float(C))
    return HourAgg(score_sum=score_sum, count=count, hour_avg=hour_avg, w_vol=w_vol)
    events = [EventContribution(score=s, weight=1.0, confidence=1.0) for s in weighted_sents]
    return aggregate_hour_weighted(events, C=C, profile="moderate")


def aggregate_hour_weighted(
    events: Iterable[EventContribution],
    C: int = 50,
    profile: str = "moderate",
) -> HourAgg:
    """
    Weighted hourly aggregation with discrete-math-friendly formulas:
      scoreSum = Σ s_i
      weightedScoreSum = Σ (s_i * w_i)
      hourAvg = clamp(scoreSum / N)
      weightedHourAvg = clamp(weightedScoreSum / Σ w_i)
      w_vol = min(1, N / C)
      effective_n = (Σ w_i)^2 / Σ w_i^2
    """
    params = HOUR_RISK_PROFILES.get(profile, HOUR_RISK_PROFILES["moderate"])
    clip = float(params["clip"])
    w_pow = float(params["weight_power"])
    c_pow = float(params["conf_power"])
    c_eps = float(params["conf_eps"])

    C_eff = float(C) if isinstance(C, (int, float)) and C > 0 else float(params["volume_cap"])
    C_eff = max(1.0, C_eff)

    score_sum = 0.0
    weighted_score_sum = 0.0
    weight_sum = 0.0
    weight_sq_sum = 0.0
    conf_sum = 0.0
    conf_weighted_sum = 0.0
    clipped_count = 0
    count = 0
    min_score: Optional[float] = None
    max_score: Optional[float] = None

    for e in events:
        raw_score = float(e.score)
        score = clamp(raw_score, -clip, clip)
        if score != raw_score:
            clipped_count += 1

        w_raw = max(0.0, float(e.weight))
        conf = clamp(float(e.confidence), 0.0, 1.0)
        w_eff = (w_raw ** w_pow) * ((conf + c_eps) ** c_pow)

        score_sum += score
        weighted_score_sum += score * w_eff
        weight_sum += w_eff
        weight_sq_sum += w_eff * w_eff
        conf_sum += conf
        conf_weighted_sum += conf * w_eff
        count += 1

        min_score = score if min_score is None else min(min_score, score)
        max_score = score if max_score is None else max(max_score, score)

    if count == 0:
        return HourAgg(
            score_sum=0.0,
            count=0,
            hour_avg=0.0,
            w_vol=0.0,
        )

    hour_avg = clamp(score_sum / float(count), -1.0, 1.0)
    weighted_hour_avg = 0.0 if weight_sum <= 0 else clamp(weighted_score_sum / weight_sum, -1.0, 1.0)
    w_vol = min(1.0, float(count) / C_eff)
    avg_conf = conf_sum / float(count)
    weighted_conf = 0.0 if weight_sum <= 0 else (conf_weighted_sum / weight_sum)
    hour_conf = clamp(weighted_conf * w_vol, 0.0, 1.0)
    effective_n = 0.0 if weight_sq_sum <= 0 else ((weight_sum * weight_sum) / weight_sq_sum)

    return HourAgg(
        score_sum=score_sum,
        count=count,
        hour_avg=hour_avg,
        w_vol=w_vol,
        weighted_score_sum=weighted_score_sum,
        weighted_hour_avg=weighted_hour_avg,
        weight_sum=weight_sum,
        avg_confidence=avg_conf,
        weighted_confidence=weighted_conf,
        hour_confidence=hour_conf,
        clipped_count=clipped_count,
        min_score=0.0 if min_score is None else min_score,
        max_score=0.0 if max_score is None else max_score,
        effective_n=effective_n,
    )


def aggregate_from_scores_weights(
    scores: List[float],
    weights: Optional[List[float]] = None,
    confidences: Optional[List[float]] = None,
    C: int = 50,
    profile: str = "moderate",
) -> HourAgg:
    """
    Convenience helper for arrays:
      score_i ∈ [-1, +1], weight_i ≥ 0, confidence_i ∈ [0, 1]
    """
    weights = weights or [1.0 for _ in scores]
    confidences = confidences or [1.0 for _ in scores]
    events = [
        EventContribution(score=s, weight=w, confidence=c)
        for s, w, c in zip(scores, weights, confidences)
    ]
    return aggregate_hour_weighted(events, C=C, profile=profile)
