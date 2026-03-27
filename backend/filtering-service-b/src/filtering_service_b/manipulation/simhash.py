from __future__ import annotations

FNV_OFFSET_BASIS_64 = 0xCBF29CE484222325
FNV_PRIME_64 = 0x100000001B3
MASK_64 = 0xFFFFFFFFFFFFFFFF
SIMHASH_BITS = 64


def simhash64(text: str) -> int:
    if not text or not text.strip():
        return 0

    vec = [0] * SIMHASH_BITS
    for token in text.split():
        if len(token) < 3:
            continue
        token_hash = _token_hash64(token)
        for bit in range(SIMHASH_BITS):
            if (token_hash >> bit) & 1:
                vec[bit] += 1
            else:
                vec[bit] -= 1

    fingerprint = 0
    for bit in range(SIMHASH_BITS):
        if vec[bit] >= 0:
            fingerprint |= 1 << bit
    return fingerprint & MASK_64


def simhash64_unsigned_str(text: str) -> str:
    return str(simhash64(text))


def _token_hash64(token: str) -> int:
    h = FNV_OFFSET_BASIS_64
    for b in token.encode("utf-8", errors="replace"):
        h ^= b
        h = (h * FNV_PRIME_64) & MASK_64
    return h
