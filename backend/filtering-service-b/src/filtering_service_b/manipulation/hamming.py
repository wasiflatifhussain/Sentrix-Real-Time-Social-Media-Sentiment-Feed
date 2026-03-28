from __future__ import annotations

MASK_64 = 0xFFFFFFFFFFFFFFFF


def hamming_distance_64(a: int, b: int) -> int:
    return ((a & MASK_64) ^ (b & MASK_64)).bit_count()
