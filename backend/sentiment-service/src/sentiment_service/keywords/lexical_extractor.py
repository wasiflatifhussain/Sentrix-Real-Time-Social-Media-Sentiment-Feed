from __future__ import annotations

import re
from collections import Counter

from sentiment_service.keywords.base import KeywordCandidate
from sentiment_service.keywords.normalizer import (
    finalize_keyword_candidates,
    is_keyword_phrase_valid,
    preprocess_keyword_text,
)

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9]{1,}")


class LexicalKeywordExtractor:
    def __init__(self, max_keywords: int = 10) -> None:
        self.max_keywords = max_keywords

    def extract_candidates(
        self,
        text: str,
        *,
        ticker: str | None = None,
        source: str | None = None,
    ) -> list[KeywordCandidate]:
        prepared = preprocess_keyword_text(text)
        tokens = [token.lower() for token in _WORD_RE.findall(prepared)]
        counts = Counter(token for token in tokens if is_keyword_phrase_valid(token))
        return [
            KeywordCandidate(phrase=token, score=float(count))
            for token, count in counts.items()
        ]

    def extract(
        self,
        text: str,
        *,
        ticker: str | None = None,
        source: str | None = None,
    ) -> list[str]:
        return finalize_keyword_candidates(
            self.extract_candidates(text, ticker=ticker, source=source),
            max_keywords=self.max_keywords,
        )
