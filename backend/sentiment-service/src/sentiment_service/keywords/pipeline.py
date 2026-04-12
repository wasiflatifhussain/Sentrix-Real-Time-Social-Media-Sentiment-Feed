from __future__ import annotations

from sentiment_service.keywords.base import KeywordCandidate, KeywordExtractor
from sentiment_service.keywords.refiner import KeywordRefiner


class KeywordPipeline:
    def __init__(
        self,
        *,
        extractor: KeywordExtractor,
        refiner: KeywordRefiner,
    ) -> None:
        self.extractor = extractor
        self.refiner = refiner

    def extract_candidates(
        self,
        text: str,
        *,
        ticker: str | None = None,
        source: str | None = None,
    ) -> list[KeywordCandidate]:
        return self.extractor.extract_candidates(
            text,
            ticker=ticker,
            source=source,
        )

    def extract(
        self,
        text: str,
        *,
        ticker: str | None = None,
        source: str | None = None,
    ) -> list[str]:
        candidates = self.extract_candidates(
            text,
            ticker=ticker,
            source=source,
        )
        return self.refiner.refine(
            text=text,
            candidates=candidates,
            ticker=ticker,
            source=source,
        )
