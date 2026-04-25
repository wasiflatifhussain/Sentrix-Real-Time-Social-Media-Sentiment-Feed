from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Protocol

from sentiment_service.keywords.base import KeywordCandidate
from sentiment_service.keywords.normalizer import (
    finalize_keyword_candidates,
    finalize_keyword_phrases,
)

log = logging.getLogger(__name__)
DEFAULT_OPENROUTER_MODEL = "qwen/qwen-2.5-7b-instruct"

if TYPE_CHECKING:
    from sentiment_service.llm_connector import OpenRouterQwenClient

KEYWORD_REFINER_SYSTEM_PROMPT = """
You refine finance-related keyword candidates for a single event.
Return only a JSON object with one key:
- keywords: an array of short finance-relevant keyword phrases

Rules:
- Keep only the most useful market, company, product, macro, or event-driver phrases.
- Remove generic conversational words, stopwords, pronouns, filler, and duplicates.
- Normalize phrases into concise finance wording where possible.
- Prefer 1 to 3 word phrases unless a longer phrase is clearly better.
- Return at most the requested number of keywords.
""".strip()


class KeywordRefiner(Protocol):
    def refine(
        self,
        *,
        text: str,
        candidates: list[KeywordCandidate],
        ticker: str | None = None,
        source: str | None = None,
    ) -> list[str]: ...


class NoopKeywordRefiner:
    def __init__(self, *, max_keywords: int) -> None:
        self.max_keywords = max_keywords

    def refine(
        self,
        *,
        text: str,
        candidates: list[KeywordCandidate],
        ticker: str | None = None,
        source: str | None = None,
    ) -> list[str]:
        return finalize_keyword_candidates(
            candidates,
            max_keywords=self.max_keywords,
        )


class LlmKeywordRefiner(NoopKeywordRefiner):
    def __init__(
        self,
        *,
        api_key: str | None,
        max_keywords: int,
        model: str | None = None,
        max_candidates: int = 15,
        temperature: float = 0.0,
        http_referer: str | None = None,
        app_title: str | None = None,
    ) -> None:
        super().__init__(max_keywords=max_keywords)
        self.max_candidates = max_candidates
        self.temperature = temperature
        from sentiment_service.llm_connector import OpenRouterQwenClient

        self.client = OpenRouterQwenClient(
            api_key=api_key,
            model=model or os.getenv("KEYWORD_LLM_MODEL", DEFAULT_OPENROUTER_MODEL),
            http_referer=http_referer,
            app_title=app_title or "sentiment-service-keywords",
        )
        if self.client.client is None:
            log.warning("Keyword LLM refiner is unavailable; falling back to Stage 1 keywords")

    def _candidate_phrases(self, candidates: list[KeywordCandidate]) -> list[str]:
        return finalize_keyword_candidates(
            candidates,
            max_keywords=self.max_candidates,
        )

    def _user_prompt(
        self,
        *,
        text: str,
        candidates: list[str],
        ticker: str | None,
        source: str | None,
    ) -> str:
        payload = {
            "ticker": (ticker or "").strip().upper() or None,
            "source": (source or "").strip().upper() or None,
            "max_keywords": self.max_keywords,
            "text": text,
            "stage1_candidates": candidates,
        }
        return json.dumps(payload, ensure_ascii=True)

    def refine(
        self,
        *,
        text: str,
        candidates: list[KeywordCandidate],
        ticker: str | None = None,
        source: str | None = None,
    ) -> list[str]:
        stage1_keywords = super().refine(
            text=text,
            candidates=candidates,
            ticker=ticker,
            source=source,
        )
        if not stage1_keywords:
            return []
        if self.client.client is None:
            return stage1_keywords

        try:
            payload = self.client.chat_json(
                system_prompt=KEYWORD_REFINER_SYSTEM_PROMPT,
                user_prompt=self._user_prompt(
                    text=text,
                    candidates=self._candidate_phrases(candidates),
                    ticker=ticker,
                    source=source,
                ),
                temperature=self.temperature,
            )
            keywords = payload.get("keywords", [])
            if not isinstance(keywords, list):
                raise ValueError("keywords must be a JSON array")
            refined = finalize_keyword_phrases(
                [str(keyword) for keyword in keywords],
                max_keywords=self.max_keywords,
            )
            if refined:
                return refined
        except Exception:
            log.exception(
                "Keyword LLM refinement failed; falling back to Stage 1 keywords "
                "ticker=%s source=%s",
                ticker,
                source,
            )

        return stage1_keywords
