from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
from typing import Dict, Iterable, List, Optional


@dataclass
class TickerState:
    signal: float
    last_hour_start_utc: int
    signal_confidence: float = 0.0


@dataclass
class HourlyRow:
    ticker: str
    hour_start_utc: int
    hour_end_utc: int
    count: int
    score_sum: float
    updated_at_utc: Optional[int] = None

    @property
    def avg_score(self) -> float:
        return 0.0 if self.count <= 0 else (self.score_sum / float(self.count))


@dataclass
class TickerSignalSnapshot:
    ticker: str
    hour_start_utc: int
    signal: float
    confidence: float
    delta_1h: Optional[float] = None
    delta_24h: Optional[float] = None


RISK_PROFILES = {
    "conservative": {
        "half_life_hours": 72.0,
        "neutral_half_life_hours": 96.0,
        "volume_cap": 80.0,
        "min_volume_weight": 0.10,
    },
    "moderate": {
        "half_life_hours": 24.0,
        "neutral_half_life_hours": 72.0,
        "volume_cap": 50.0,
        "min_volume_weight": 0.05,
    },
    "aggressive": {
        "half_life_hours": 6.0,
        "neutral_half_life_hours": 48.0,
        "volume_cap": 30.0,
        "min_volume_weight": 0.02,
    },
}


def alpha_from_half_life_hours(H: float) -> float:
    """
    EMA half-life:
      alpha = 1 - 2^(-1 / H)
    """
    H = max(1e-6, float(H))
    return 1.0 - math.pow(2.0, (-1.0 / H))


def update_signal(prev_signal: float, hour_avg: float, w_vol: float, alpha_base: float) -> float:
    """
    EMA update:
      S_t = (1 - alpha_eff) * S_{t-1} + alpha_eff * X_t
      alpha_eff = alpha_base * w_vol
      X_t = hourAvg
    """
    alpha_eff = clamp(alpha_base * w_vol, 0.0, 1.0)
    return (1.0 - alpha_eff) * prev_signal + alpha_eff * hour_avg


def _volume_weight(count: int, cap: float, min_w: float) -> float:
    if cap <= 0:
        return 1.0
    w = min(1.0, float(count) / cap)
    return max(min_w, w)


def _decay_toward_neutral(signal: float, gap_hours: float, half_life_hours: float) -> float:
    """
    Missing-hour decay (toward 0):
      decay = 2^(-gap / halfLife)
      signal_t = signal_{t-1} * decay
    """
    if gap_hours <= 0:
        return signal
    half_life_hours = max(1e-6, float(half_life_hours))
    decay = math.pow(2.0, -gap_hours / half_life_hours)
    return signal * decay


def normalize_hourly_row(raw: dict) -> Optional[HourlyRow]:
    if not isinstance(raw, dict):
        return None
    ticker = str(raw.get("ticker", "") or "").strip().upper()
    if not ticker:
        return None
    hour_start = int(raw.get("hourStartUtc", 0) or 0)
    hour_end = int(raw.get("hourEndUtc", 0) or 0)
    count = int(raw.get("count", 0) or 0)
    score_sum = float(raw.get("scoreSum", 0.0) or 0.0)
    updated = raw.get("updatedAtUtc")
    updated_at_utc = int(updated) if updated is not None else None
    return HourlyRow(
        ticker=ticker,
        hour_start_utc=hour_start,
        hour_end_utc=hour_end,
        count=count,
        score_sum=score_sum,
        updated_at_utc=updated_at_utc,
    )


def group_hourly_rows(rows: Iterable[dict]) -> Dict[str, List[HourlyRow]]:
    """
    Group by ticker, sort by hourStartUtc.
    Timestamps are in seconds (datetime.utcfromtimestamp with NO *1000).
    """
    grouped: Dict[str, List[HourlyRow]] = {}
    for raw in rows:
        row = normalize_hourly_row(raw)
        if not row:
            continue
        grouped.setdefault(row.ticker, []).append(row)
    for t in grouped:
        grouped[t].sort(key=lambda r: r.hour_start_utc)
    return grouped


def compute_signal_series(
    rows: List[HourlyRow],
    *,
    profile: str = "moderate",
    max_hours: Optional[int] = 168,
    prev_state: Optional[TickerState] = None,
) -> List[TickerSignalSnapshot]:
    """
    Incremental per-hour EMA using available rows only:
      - group by ticker before calling
      - sort by hourStartUtc
      - if max_hours provided, keep the last N rows only
    """
    if not rows:
        return []

    rows = sorted(rows, key=lambda r: r.hour_start_utc)
    if max_hours is not None and len(rows) > max_hours:
        rows = rows[-int(max_hours):]

    params = RISK_PROFILES.get(profile, RISK_PROFILES["moderate"])
    alpha_base = alpha_from_half_life_hours(params["half_life_hours"])
    volume_cap = float(params["volume_cap"])
    min_w = float(params["min_volume_weight"])
    neutral_half_life = float(params["neutral_half_life_hours"])

    if prev_state:
        signal = float(prev_state.signal)
        conf = float(prev_state.signal_confidence)
        last_hour = int(prev_state.last_hour_start_utc)
    else:
        signal = 0.0
        conf = 0.0
        last_hour = None

    series: List[TickerSignalSnapshot] = []
    for row in rows:
        if last_hour is not None:
            gap_hours = (row.hour_start_utc - last_hour) / 3600.0 - 1.0
            if gap_hours > 0:
                signal = _decay_toward_neutral(signal, gap_hours, neutral_half_life)
                conf = _decay_toward_neutral(conf, gap_hours, neutral_half_life)

        hour_avg = clamp(row.avg_score, -1.0, 1.0)
        w_vol = _volume_weight(row.count, volume_cap, min_w)
        signal = update_signal(signal, hour_avg, w_vol, alpha_base)

        hour_conf = _volume_weight(row.count, volume_cap, min_w)
        conf = update_signal(conf, hour_conf, w_vol, alpha_base)

        series.append(
            TickerSignalSnapshot(
                ticker=row.ticker,
                hour_start_utc=row.hour_start_utc,
                signal=signal,
                confidence=clamp(conf, 0.0, 1.0),
            )
        )
        last_hour = row.hour_start_utc

    return series


def latest_snapshot_with_deltas(series: List[TickerSignalSnapshot]) -> Optional[TickerSignalSnapshot]:
    if not series:
        return None
    latest = series[-1]
    if len(series) > 1:
        latest.delta_1h = latest.signal - series[-2].signal
    hour_index = {s.hour_start_utc: s for s in series}
    target_24h = latest.hour_start_utc - 24 * 3600
    if target_24h in hour_index:
        latest.delta_24h = latest.signal - hour_index[target_24h].signal
    return latest


def compute_signal_for_ticker(
    rows: List[HourlyRow],
    *,
    profile: str = "moderate",
    max_hours: Optional[int] = 168,
    prev_state: Optional[TickerState] = None,
) -> Optional[TickerSignalSnapshot]:
    series = compute_signal_series(rows, profile=profile, max_hours=max_hours, prev_state=prev_state)
    return latest_snapshot_with_deltas(series)


def compute_signals_from_history(
    history_rows: Iterable[dict],
    *,
    profile: str = "moderate",
    max_hours: Optional[int] = 168,
) -> Dict[str, TickerSignalSnapshot]:
    """
    For testing: use whatever history exists (no assumption of exactly 167/168 rows).
    """
    grouped = group_hourly_rows(history_rows)
    out: Dict[str, TickerSignalSnapshot] = {}
    for ticker, rows in grouped.items():
        snap = compute_signal_for_ticker(rows, profile=profile, max_hours=max_hours)
        if snap:
            out[ticker] = snap
    return out


RISK_HALF_LIFE_HOURS = {
    "conservative": 72.0,
    "moderate": 24.0,
    "aggressive": 6.0,
}


def utc_hour_label(hour_start_utc: int) -> str:
    """
    Helper for seconds-based timestamps (no *1000).
    """
    return datetime.utcfromtimestamp(int(hour_start_utc)).isoformat() + "Z"











######################################
######################################
######################################
######################################
######################################



"""
Ticker-level sentiment aggregation

This module aggregates hourly sentiment signals into ticker-level signals.

Core formula:

    rawTickerScore =
        sum( W_t * S_t ) / sum( W_t )

where

    S_t = hour-level sentiment score
    W_t = recency_weight * quality_weight

Then confidence shrinkage is applied:

    tickerScore = shrinkage * rawTickerScore

where

    shrinkage = min(1, effective_hours / min_effective_hours)

All timestamps are stored as UNIX time in SECONDS.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from math import isfinite
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

@dataclass
class TickerAggregationConfig:
    lookback_hours: int = 168            # 7 days
    half_life_hours: float = 24.0        # recency decay half-life
    min_event_count: int = 5             # quality normalization
    min_effective_hours: float = 8.0     # shrinkage threshold
    clamp_score: bool = True


# ---------------------------------------------------------
# Utility functions
# ---------------------------------------------------------

def _safe_float(value: Any) -> Optional[float]:
    try:
        x = float(value)
        return x if isfinite(x) else None
    except (TypeError, ValueError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------
# Hour-level helpers
# ---------------------------------------------------------

def _derive_hour_score(row: Dict[str, Any]) -> Optional[float]:
    """
    Obtain hour-level score.

    hourScore = scoreSum / count if count > 0 else 0.  # 이걸 hour level aggregation 계산할 때 넣고, mongoDB에 hourly score 저장될 떄 hourScore도 같이 저장

    Prefer stored hourScore.
    Otherwise compute from scoreSum / count.
    """

    hour_score = _safe_float(row.get("hourScore"))
    if hour_score is not None:
        return max(-1.0, min(1.0, hour_score))

    score_sum = _safe_float(row.get("scoreSum"))
    count = _safe_float(row.get("count"))

    if score_sum is None or count is None or count <= 0:
        return None

    derived = score_sum / count

    return max(-1.0, min(1.0, derived))


def _get_hour_timestamp(row: Dict[str, Any]) -> Optional[int]:
    """
    Mongo timestamps are UNIX seconds.
    Prefer hourEndUtc then hourStartUtc.
    """

    ts = row.get("hourEndUtc", row.get("hourStartUtc"))
    return _safe_int(ts)


def _age_in_hours(now_seconds: int, hour_seconds: int) -> float:
    return max(0.0, (now_seconds - hour_seconds) / 3600.0)


# ---------------------------------------------------------
# Weight functions
# ---------------------------------------------------------

def _recency_weight(age_hours: float, half_life_hours: float) -> float:
    """
    Exponential half-life decay.

    w = 2^(-age / half_life)
    """
    return 2.0 ** (-age_hours / half_life_hours)


def _quality_weight(row: Dict[str, Any], min_event_count: int) -> float:
    """
    Hour-quality weight based on event count.
    """

    count = _safe_float(row.get("count"))

    if count is None or count <= 0:
        return 0.0

    return max(0.0, min(1.0, count / float(min_event_count)))


def _effective_sample_size(weights: List[float]) -> float:
    """
    Effective sample size (ESS)

        (sum w)^2 / sum(w^2)
    """

    if not weights:
        return 0.0

    s1 = sum(weights)
    s2 = sum(w * w for w in weights)

    if s2 == 0:
        return 0.0

    return (s1 * s1) / s2


# ---------------------------------------------------------
# Source breakdown merger
# ---------------------------------------------------------

def _merge_source_breakdown(rows: List[Dict[str, Any]]) -> Dict[str, int]:

    merged: Dict[str, int] = defaultdict(int)

    for row in rows:

        breakdown = row.get("sourceBreakdown")

        if not isinstance(breakdown, dict):
            continue

        for source, count in breakdown.items():

            try:
                merged[str(source)] += int(count)
            except (TypeError, ValueError):
                continue

    return dict(merged)


# ---------------------------------------------------------
# Main aggregation function
# ---------------------------------------------------------

def aggregate_ticker_scores(
    hourly_rows: List[Dict[str, Any]],
    now_utc_seconds: Optional[int] = None,
    config: Optional[TickerAggregationConfig] = None,
) -> List[Dict[str, Any]]:

    cfg = config or TickerAggregationConfig()

    # Infer "now" from latest hour if not provided
    if now_utc_seconds is None:

        timestamps = [_get_hour_timestamp(r) for r in hourly_rows]
        timestamps = [t for t in timestamps if t is not None]

        if not timestamps:
            return []

        now_utc_seconds = max(timestamps)

    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for row in hourly_rows:

        ticker = row.get("ticker")

        if not ticker:
            continue

        grouped[str(ticker)].append(row)

    results: List[Dict[str, Any]] = []

    for ticker, rows in grouped.items():

        weighted_sum = 0.0
        total_weight = 0.0
        weights: List[float] = []

        hours_used = 0

        rows_sorted = sorted(
            rows,
            key=lambda r: _get_hour_timestamp(r) or 0,
            reverse=True,
        )

        recent_hour_score: Optional[float] = None
        recent_hour_start: Optional[int] = None

        for row in rows_sorted:

            hour_score = _derive_hour_score(row)
            ts = _get_hour_timestamp(row)

            if hour_score is None or ts is None:
                continue

            age_hours = _age_in_hours(now_utc_seconds, ts)

            if age_hours >= cfg.lookback_hours:
                continue

            recency_w = _recency_weight(age_hours, cfg.half_life_hours)
            quality_w = _quality_weight(row, cfg.min_event_count)

            w = recency_w * quality_w

            if w <= 0:
                continue

            if recent_hour_start is None:

                recent_hour_start = _safe_int(row.get("hourStartUtc"))
                recent_hour_score = hour_score

            weighted_sum += w * hour_score
            total_weight += w

            weights.append(w)
            hours_used += 1

        if total_weight <= 0:
            continue

        raw_ticker_score = weighted_sum / total_weight

        if cfg.clamp_score:
            raw_ticker_score = max(-1.0, min(1.0, raw_ticker_score))

        effective_hours = _effective_sample_size(weights)

        shrinkage = min(1.0, effective_hours / cfg.min_effective_hours)

        ticker_score = shrinkage * raw_ticker_score

        if cfg.clamp_score:
            ticker_score = max(-1.0, min(1.0, ticker_score))

        results.append({

            "_id": ticker,

            "ticker": ticker,

            "tickerScore": ticker_score,
            "rawTickerScore": raw_ticker_score,

            "shrinkageFactor": shrinkage,

            "recentHourScore": recent_hour_score,
            "recentHourStartUtc": recent_hour_start,

            "hoursUsed": hours_used,
            "lookbackHours": cfg.lookback_hours,
            "halfLifeHours": cfg.half_life_hours,

            "weightedHourlyScoreSum": weighted_sum,
            "totalHourlyWeight": total_weight,

            "effectiveHours": effective_hours,

            "sourceBreakdown": _merge_source_breakdown(rows_sorted),

            "createdAtUtc": now_utc_seconds,
        })

    return sorted(results, key=lambda x: x["ticker"])