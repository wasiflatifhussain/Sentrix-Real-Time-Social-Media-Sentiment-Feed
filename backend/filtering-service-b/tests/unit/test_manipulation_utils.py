from filtering_service_b.manipulation.hamming import hamming_distance_64
from filtering_service_b.manipulation.simhash import simhash64


def test_simhash_same_text_same_fingerprint() -> None:
    text = "Tesla earnings growth and valuation discussion for TSLA shares"
    assert simhash64(text) == simhash64(text)


def test_simhash_blank_text_returns_zero() -> None:
    assert simhash64("") == 0
    assert simhash64("   \n\t  ") == 0


def test_hamming_distance_basic() -> None:
    a = simhash64("TSLA earnings and revenue beat estimates")
    b = simhash64("TSLA earnings and revenue beat estimates")
    c = simhash64("Weekend recipe and kitchen notes only")

    assert hamming_distance_64(a, b) == 0
    assert hamming_distance_64(a, c) >= 1
