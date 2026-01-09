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
