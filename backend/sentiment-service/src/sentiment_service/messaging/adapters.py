from __future__ import annotations

from sentiment_service.domain.models import CleanedEvent as DomainCleanedEvent
from sentiment_service.messaging.schemas import CleanedEvent as TransportCleanedEvent


def to_domain_event(e: TransportCleanedEvent) -> DomainCleanedEvent:
    if e.created_at_utc is None:
        raise ValueError("createdAtUtc is required to build domain CleanedEvent")
    if not isinstance(e.created_at_utc, int):
        raise ValueError("createdAtUtc must be int epoch seconds")

    return DomainCleanedEvent(
        event_id=e.event_id,
        ticker=e.ticker,
        source=e.source,
        entity_type=e.entity_type,
        created_at_utc=e.created_at_utc,
        text_normalized=e.text_normalized,
    )
