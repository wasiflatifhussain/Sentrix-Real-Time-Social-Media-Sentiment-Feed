from __future__ import annotations

import logging
import os

from sentiment_service.config.settings import KeywordSettings
from sentiment_service.keywords.base import KeywordExtractor
from sentiment_service.keywords.embedding_service import (
    SentenceTransformerEmbeddingService,
)
from sentiment_service.keywords.keybert_extractor import KeyBertKeywordExtractor
from sentiment_service.keywords.lexical_extractor import LexicalKeywordExtractor
from sentiment_service.keywords.pipeline import KeywordPipeline
from sentiment_service.keywords.refiner import LlmKeywordRefiner, NoopKeywordRefiner

log = logging.getLogger(__name__)

def build_keyword_extractor(settings: KeywordSettings) -> KeywordExtractor:
    stage1_extractor: KeywordExtractor = LexicalKeywordExtractor(
        max_keywords=settings.max_final_keywords
    )

    if settings.extractor_mode in {"stub", "lexical"}:
        log.info("Using lexical keyword extractor mode=%s", settings.extractor_mode)
    else:
        try:
            import keybert  # noqa: F401
            import sentence_transformers  # noqa: F401
        except ImportError:
            log.warning(
                "KeyBERT dependencies are not installed; falling back to lexical keyword extraction"
            )
        else:
            try:
                embedding_service = SentenceTransformerEmbeddingService(
                    model_name=settings.model_name,
                    normalize_embeddings=settings.normalize_embeddings,
                )
                stage1_extractor = KeyBertKeywordExtractor(
                    embedding_service=embedding_service,
                    max_keywords=settings.max_final_keywords,
                    top_n=settings.top_n,
                    ngram_min=settings.ngram_min,
                    ngram_max=settings.ngram_max,
                    use_mmr=settings.use_mmr,
                    diversity=settings.diversity,
                    fallback=stage1_extractor,
                )
            except Exception:
                log.exception(
                    "Failed to initialize KeyBERT extractor; falling back to lexical keyword extraction"
                )

    refiner = NoopKeywordRefiner(max_keywords=settings.max_final_keywords)
    if settings.refiner_mode == "llm":
        refiner = LlmKeywordRefiner(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            max_keywords=settings.max_final_keywords,
            model=settings.llm_model,
            max_candidates=settings.llm_max_candidates,
            temperature=settings.llm_temperature,
        )

    pipeline = KeywordPipeline(
        extractor=stage1_extractor,
        refiner=refiner,
    )
    log.info(
        "Using keyword pipeline extractor=%s refiner=%s max_keywords=%s",
        pipeline.extractor.__class__.__name__,
        pipeline.refiner.__class__.__name__,
        settings.max_final_keywords,
    )
    return pipeline
