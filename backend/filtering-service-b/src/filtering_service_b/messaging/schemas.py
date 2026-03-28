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


def _require_present(payload_fragment: dict[str, Any], key: str) -> Any:
    if (
        key not in payload_fragment
        or payload_fragment[key] is None
        or (
            isinstance(payload_fragment[key], str)
            and payload_fragment[key].strip() == ""
        )
    ):
        raise ValueError(f"Missing required field: {key}")
    return payload_fragment[key]


def parse_cleaned_event(payload: dict[str, Any]) -> CleanedEvent:
    ingestor_event = _require_present(payload, "ingestorEvent")
    text_view = _require_present(payload, "textView")

    return CleanedEvent(
        event_id=str(_require_present(ingestor_event, "eventId")),
        ticker=str(_require_present(ingestor_event, "ticker")),
        source=str(_require_present(ingestor_event, "source")),
        entity_type=str(_require_present(ingestor_event, "entityType")),
        created_at_utc=ingestor_event.get("createdAtUtc"),
        text_normalized=str(_require_present(text_view, "textNormalized")),
        title=ingestor_event.get("title"),
        author=ingestor_event.get("author"),
    )
