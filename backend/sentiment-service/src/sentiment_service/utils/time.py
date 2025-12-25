from dataclasses import dataclass
from typing import Tuple

SECONDS_PER_HOUR = 60 * 60


@dataclass(frozen=True)
class HourBucket:
    hour_start_utc: int  # epoch seconds
    hour_end_utc: int  # epoch seconds

    def as_tuple(self) -> Tuple[int, int]:
        return self.hour_start_utc, self.hour_end_utc


def bucket_epoch_seconds_to_hour(ts_utc_seconds: int) -> HourBucket:
    """
    Convert a UTC epoch-seconds timestamp into an hour-aligned bucket.

    Example:
      1766567348 -> [1766566800, 1766570400)

    Assumptions:
    - Input is UTC
    - Input is in seconds (not millis)
    """

    if ts_utc_seconds is None:
        raise ValueError("timestamp cannot be None")

    if ts_utc_seconds < 0:
        raise ValueError(f"invalid epoch seconds: {ts_utc_seconds}")

    hour_start = (ts_utc_seconds // SECONDS_PER_HOUR) * SECONDS_PER_HOUR
    hour_end = hour_start + SECONDS_PER_HOUR

    return HourBucket(
        hour_start_utc=hour_start,
        hour_end_utc=hour_end,
    )
