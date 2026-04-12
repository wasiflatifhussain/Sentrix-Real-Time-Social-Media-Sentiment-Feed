from __future__ import annotations

import logging

from sentiment_service.keywords.base import KeywordCandidate, KeywordExtractor
from sentiment_service.keywords.embedding_service import (
    SentenceTransformerEmbeddingService,
)
from sentiment_service.keywords.lexical_extractor import LexicalKeywordExtractor
from sentiment_service.keywords.normalizer import (
    finalize_keyword_candidates,
    preprocess_keyword_text,
)

log = logging.getLogger(__name__)


class KeyBertKeywordExtractor:
    def __init__(
        self,
        *,
        embedding_service: SentenceTransformerEmbeddingService,
        max_keywords: int = 10,
        top_n: int = 20,
        ngram_min: int = 1,
        ngram_max: int = 3,
        use_mmr: bool = True,
        diversity: float = 0.4,
        fallback: KeywordExtractor | None = None,
    ) -> None:
        self.embedding_service = embedding_service
        self.model_name = embedding_service.model_name
        self.max_keywords = max_keywords
        self.top_n = top_n
        self.ngram_min = ngram_min
        self.ngram_max = ngram_max
        self.use_mmr = use_mmr
        self.diversity = diversity
        self.fallback = fallback or LexicalKeywordExtractor(max_keywords=max_keywords)
        self._fallback_count = 0
        self._kw_model = None

    def _ensure_model(self):
        if self._kw_model is not None:
            return self._kw_model

        from keybert import KeyBERT

        log.info("Loading KeyBERT embedding model=%s", self.model_name)
        self._kw_model = KeyBERT(model=self.embedding_service.model)
        return self._kw_model

    def _extract_candidates(self, text: str) -> list[KeywordCandidate]:
        prepared = preprocess_keyword_text(text)
        if not prepared:
            return []

        try:
            kw_model = self._ensure_model()
            raw = kw_model.extract_keywords(
                docs=prepared,
                keyphrase_ngram_range=(self.ngram_min, self.ngram_max),
                stop_words="english",
                top_n=self.top_n,
                use_mmr=self.use_mmr,
                diversity=self.diversity,
            )
            return [
                KeywordCandidate(phrase=str(phrase), score=float(score))
                for phrase, score in raw
            ]
        except Exception:
            self._fallback_count += 1
            log.exception(
                "KeyBERT keyword extraction failed; falling back to lexical extraction "
                "model=%s fallback_count=%s",
                self.model_name,
                self._fallback_count,
            )
            return self.fallback.extract_candidates(text)

    def extract_candidates(
        self,
        text: str,
        *,
        ticker: str | None = None,
        source: str | None = None,
    ) -> list[KeywordCandidate]:
        return self._extract_candidates(text)

    def extract(
        self,
        text: str,
        *,
        ticker: str | None = None,
        source: str | None = None,
    ) -> list[str]:
        candidates = self.extract_candidates(text, ticker=ticker, source=source)
        if not candidates:
            return self.fallback.extract(text, ticker=ticker, source=source)
        return finalize_keyword_candidates(
            candidates,
            max_keywords=self.max_keywords,
        )
