from __future__ import annotations

import logging
import os

from sentiment_service.keywords.base import KeywordExtractor
from sentiment_service.keywords.keybert_extractor import KeyBertKeywordExtractor
from sentiment_service.keywords.lexical_extractor import LexicalKeywordExtractor

log = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def build_keyword_extractor_from_env() -> KeywordExtractor:
    mode = os.getenv("KEYWORD_EXTRACTOR_MODE", "keybert").strip().lower()
    max_keywords = _env_int("KEYWORD_MAX_FINAL", 10)
    lexical = LexicalKeywordExtractor(max_keywords=max_keywords)

    if mode in {"stub", "lexical"}:
        log.info("Using lexical keyword extractor mode=%s", mode)
        return lexical

    try:
        import keybert  # noqa: F401
        import sentence_transformers  # noqa: F401
    except ImportError:
        log.warning(
            "KeyBERT dependencies are not installed; falling back to lexical keyword extraction"
        )
        return lexical

    extractor = KeyBertKeywordExtractor(
        model_name=os.getenv(
            "KEYBERT_MODEL_NAME",
            "sentence-transformers/all-MiniLM-L6-v2",
        ),
        max_keywords=max_keywords,
        top_n=_env_int("KEYBERT_TOP_N", 20),
        ngram_min=_env_int("KEYBERT_NGRAM_MIN", 1),
        ngram_max=_env_int("KEYBERT_NGRAM_MAX", 3),
        use_mmr=os.getenv("KEYBERT_USE_MMR", "true").strip().lower() == "true",
        diversity=_env_float("KEYBERT_DIVERSITY", 0.4),
        fallback=lexical,
    )
    log.info(
        "Using KeyBERT keyword extractor model=%s top_n=%s max_keywords=%s",
        extractor.model_name,
        extractor.top_n,
        extractor.max_keywords,
    )
    return extractor
