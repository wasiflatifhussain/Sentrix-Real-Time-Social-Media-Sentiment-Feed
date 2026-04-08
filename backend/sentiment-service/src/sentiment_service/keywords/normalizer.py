from __future__ import annotations

import re

from sentiment_service.keywords.base import KeywordCandidate

_URL_RE = re.compile(r"(https?://\S+|<url>)", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^a-z0-9&+./\-\s]")
_GENERIC_SINGLE_WORDS = {
    "http",
    "https",
    "post",
    "comment",
    "reddit",
    "url",
    "user",
    "wallstreetbets",
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
    if len(tokens) == 1 and normalized in _GENERIC_SINGLE_WORDS:
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
