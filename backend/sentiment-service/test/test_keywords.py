from sentiment_service.keywords.keybert_extractor import KeyBertKeywordExtractor
from sentiment_service.keywords.normalizer import finalize_keyword_candidates
from sentiment_service.keywords.base import KeywordCandidate


def test_finalize_keyword_candidates_normalizes_and_deduplicates():
    candidates = [
        KeywordCandidate(" Earnings ", 0.92),
        KeywordCandidate("earnings", 0.85),
        KeywordCandidate("Guidance Cut", 0.80),
        KeywordCandidate("<URL>", 0.99),
    ]

    keywords = finalize_keyword_candidates(candidates, max_keywords=5)

    assert keywords == ["earnings", "guidance cut"]


def test_keybert_extractor_falls_back_when_backend_fails(monkeypatch):
    extractor = KeyBertKeywordExtractor(max_keywords=5)

    def raise_backend_error():
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr(extractor, "_ensure_model", raise_backend_error)

    keywords = extractor.extract(
        "Tesla earnings beat expectations and guidance improved."
    )

    assert "earnings" in keywords
    assert len(keywords) <= 5
