from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class FilterMeta:
    filter_stage: str
    decision: str
    filter_reason: Optional[str]
    processed_at_utc: Optional[int]


@dataclass(frozen=True)
class CleanedEvent:
    event_id: str
    dedup_key: Optional[str]
    ticker: str
    source: str
    entity_type: str
    created_at_utc: Optional[int]
    ingested_at_utc: Optional[int]
    text_normalized: str
    title: Optional[str]
    author: Optional[str]
    filter_meta: Optional[FilterMeta]


def _require(d: dict[str, Any], key: str) -> Any:
    if (
        key not in d
        or d[key] is None
        or (isinstance(d[key], str) and d[key].strip() == "")
    ):
        raise ValueError(f"Missing required field: {key}")
    return d[key]


def parse_cleaned_event(payload: dict[str, Any]) -> CleanedEvent:
    # Envelope shape from Filtering Service:
    # {
    #   "ingestorEvent": {...},
    #   "filterMeta": {...},
    #   "textView": {"textNormalized": "...", ...},
    #   ...
    # }

    ing = _require(payload, "ingestorEvent")
    tv = _require(payload, "textView")

    event_id = _require(ing, "eventId")
    ticker = _require(ing, "ticker")
    source = _require(ing, "source")
    entity_type = _require(ing, "entityType")
    text_norm = _require(tv, "textNormalized")

    fm = payload.get("filterMeta")
    filter_meta = None
    if isinstance(fm, dict):
        filter_meta = FilterMeta(
            filter_stage=(
                str(fm.get("filterStage"))
                if fm.get("filterStage") is not None
                else "unknown"
            ),
            decision=(
                str(fm.get("decision")) if fm.get("decision") is not None else "unknown"
            ),
            filter_reason=fm.get("filterReason"),
            processed_at_utc=fm.get("processedAtUtc"),
        )

    return CleanedEvent(
        event_id=str(event_id),
        dedup_key=ing.get("dedupKey"),
        ticker=str(ticker),
        source=str(source),
        entity_type=str(entity_type),
        created_at_utc=ing.get("createdAtUtc"),
        ingested_at_utc=ing.get("ingestedAtUtc"),
        text_normalized=str(text_norm),
        title=ing.get("title"),
        author=ing.get("author"),
        filter_meta=filter_meta,
    )
