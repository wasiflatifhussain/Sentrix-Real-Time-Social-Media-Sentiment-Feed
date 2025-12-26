from __future__ import annotations

import hashlib


def placeholder_signal_score(*, ticker: str, hour_start_utc: int) -> float:
    """
    Stub signal score generator.

    This placeholder is replaced later by EMA/EWMA applied to hourly aggregates.
    Output is deterministic in [-1, 1] for a given (ticker, hour_start_utc).
    """
    basis = f"{ticker}|{hour_start_utc}".encode("utf-8", errors="replace")
    h = hashlib.sha256(basis).digest()
    n = int.from_bytes(h[:8], "big")
    x = (n % 20001) / 10000.0  # 0..2
    return x - 1.0  # -1..+1
