from __future__ import annotations

import re

from sentiment_service.keywords.base import KeywordCandidate

_URL_RE = re.compile(r"(https?://\S+|<url>)", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9&+./\-\s]")
_GENERIC_SINGLE_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "http",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "https",
    "or",
    "post",
    "comment",
    "she",
    "so",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "us",
    "reddit",
    "url",
    "user",
    "was",
    "wallstreetbets",
    "we",
    "were",
    "with",
    "you",
    "your",
}
_ALLOWED_SINGLE_WORD_KEYWORDS = {
    # tracked ticker / company whitelist
    "tesla",
    "tsla",
    "apple",
    "aapl",
    "microsoft",
    "msft",
    "nvidia",
    "nvda",
    "amazon",
    "amzn",
    "google",
    "alphabet",
    "googl",
    "meta",
    "berkshire",
    "brkb",
    "jpmorgan",
    "jpm",
    "visa",
    "mastercard",
    "walmart",
    "wmt",
    "lilly",
    "eli",
    "lly",
    "exxon",
    "mobil",
    "xom",
    "johnson",
    "jnj",
    "oracle",
    "orcl",
    "broadcom",
    "avgo",
    "costco",
    "cost",
    "nike",
    "nke",
    "pfizer",
    "pfe",
    # finance terms that are still useful alone
    "earnings",
    "guidance",
    "delivery",
    "deliveries",
    "margin",
    "margins",
    "revenue",
    "sales",
    "demand",
    "supply",
    "profit",
    "profits",
    "forecast",
    "outlook",
    "estimate",
    "estimates",
    "beat",
    "beats",
    "miss",
    "misses",
    "upgrade",
    "downgrade",
    "volatility",
    "valuation",
    "growth",
    "chip",
    "chips",
    "ai",
    "bev",
    "robotaxi",
    "autonomy",
    "q1",
    "q2",
    "q3",
    "q4",
}


def preprocess_keyword_text(text: str) -> str:
    cleaned = _URL_RE.sub(" ", text or "")
    cleaned = cleaned.replace("\n", " ")
    return _WS_RE.sub(" ", cleaned).strip()


def normalize_keyword_phrase(phrase: str) -> str:
    normalized = (phrase or "").strip().lower()
    normalized = normalized.replace("_", " ").replace("$", "")
    normalized = _PUNCT_RE.sub(" ", normalized)
    normalized = _WS_RE.sub(" ", normalized).strip(" -./")
    return normalized


def is_keyword_phrase_valid(phrase: str) -> bool:
    normalized = normalize_keyword_phrase(phrase)
    if not normalized:
        return False
    if normalized.isdigit():
        return False

    tokens = normalized.split()
    if not tokens:
        return False
    if len(tokens) == 1:
        if normalized in _GENERIC_SINGLE_WORDS:
            return False
        if normalized not in _ALLOWED_SINGLE_WORD_KEYWORDS:
            return False
    if all(token in _GENERIC_SINGLE_WORDS for token in tokens):
        return False
    if all(len(token) <= 1 for token in tokens):
        return False
    return True


def finalize_keyword_candidates(
    candidates: list[KeywordCandidate],
    *,
    max_keywords: int,
) -> list[str]:
    seen: set[str] = set()
    final_keywords: list[str] = []

    ranked = sorted(candidates, key=lambda c: (-float(c.score), c.phrase.lower()))
    for candidate in ranked:
        normalized = normalize_keyword_phrase(candidate.phrase)
        if not is_keyword_phrase_valid(normalized):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        final_keywords.append(normalized)
        if len(final_keywords) >= max_keywords:
            break

    return final_keywords


def finalize_keyword_phrases(
    phrases: list[str],
    *,
    max_keywords: int,
) -> list[str]:
    return finalize_keyword_candidates(
        [
            KeywordCandidate(phrase=str(phrase), score=float(len(phrases) - index))
            for index, phrase in enumerate(phrases)
        ],
        max_keywords=max_keywords,
    )
