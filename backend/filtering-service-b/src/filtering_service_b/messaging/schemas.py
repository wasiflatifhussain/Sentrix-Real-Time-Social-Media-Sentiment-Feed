from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class CleanedEvent:
    event_id: str
    ticker: str
    source: str
    entity_type: str
    created_at_utc: Optional[int]
    text_normalized: str
    title: Optional[str]
    author: Optional[str]


def _require(d: dict[str, Any], key: str) -> Any:
    if (
        key not in d
        or d[key] is None
        or (isinstance(d[key], str) and d[key].strip() == "")
    ):
        raise ValueError(f"Missing required field: {key}")
    return d[key]


def parse_cleaned_event(payload: dict[str, Any]) -> CleanedEvent:
    # Matches the cleaned envelope currently consumed by sentiment-service.
    ing = _require(payload, "ingestorEvent")
    tv = _require(payload, "textView")

    return CleanedEvent(
        event_id=str(_require(ing, "eventId")),
        ticker=str(_require(ing, "ticker")),
        source=str(_require(ing, "source")),
        entity_type=str(_require(ing, "entityType")),
        created_at_utc=ing.get("createdAtUtc"),
        text_normalized=str(_require(tv, "textNormalized")),
        title=ing.get("title"),
        author=ing.get("author"),
    )
