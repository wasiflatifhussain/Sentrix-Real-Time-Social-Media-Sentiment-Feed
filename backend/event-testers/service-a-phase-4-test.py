"""
seed_phase4_dedup_events.py

Publishes test IngestorEvent JSON messages into RAW topic to verify Phase 4 EXACT DEDUP.

This seeder is GUARANTEED to work with:
- combineText(title + "\n" + text)
- Normalizer
- bucket-based content hash
- ID-based dedup

Covers:
- EXACT_DUP_EVENT_ID
- EXACT_DUP_CONTENT
- Same content, different ticker (KEEP)
- Same content, different bucket (KEEP)
- Unique content (KEEP)

NOTE:
IDs suffixed with "b" to avoid Redis pollution.
"""

import json
import time
from kafka import KafkaProducer

BOOTSTRAP = "localhost:9092"
RAW_TOPIC = "sentrix.ingestor.events"


def now_epoch() -> int:
    return int(time.time())


BASE_TITLE = "Phase4 baseline"
BASE_TEXT = "TSLA looks strong here. Earnings were solid. https://example.com"


def mk_event(event_id: str, *, title: str, text: str, ticker: str, created_at: int):
    return {
        "eventVersion": 1,
        "source": "REDDIT",
        "entityType": "POST",
        "eventId": event_id,
        "dedupKey": event_id,
        "createdAtUtc": created_at,
        "ingestedAtUtc": created_at,
        "ticker": ticker,
        "community": "stocks",
        "author": "phase4_user",
        "title": title,
        "text": text,
        "contentUrl": f"https://reddit.com/{event_id}",
        "platform": {
            "id": event_id.split(":")[-1],
            "fullName": event_id,
            "permalink": f"/r/stocks/comments/{event_id}",
            "rawUrl": f"https://reddit.com/{event_id}",
        },
        "thread": None,
        "metrics": {"likeCount": 1},
        "capture": {"query": f"${ticker}", "fetchedFrom": "r/stocks"},
        "lang": None,
    }


def build_events():
    now = now_epoch()

    return [
        # 1) KEEP — baseline
        mk_event(
            "reddit:t3_phase4_01b",
            title=BASE_TITLE,
            text=BASE_TEXT,
            ticker="TSLA",
            created_at=now,
        ),

        # 2) DROP — EXACT_DUP_EVENT_ID (same ID)
        mk_event(
            "reddit:t3_phase4_01b",
            title=BASE_TITLE,
            text=BASE_TEXT,
            ticker="TSLA",
            created_at=now,
        ),

        # 3) DROP — EXACT_DUP_CONTENT (same normalized text, same bucket, diff ID)
        mk_event(
            "reddit:t3_phase4_02b",
            title=BASE_TITLE,  # MUST MATCH
            text=BASE_TEXT,  # MUST MATCH
            ticker="TSLA",  # MUST MATCH
            created_at=now + 30,  # same bucket (1h)
        ),

        # 4) KEEP — same content, DIFFERENT ticker
        mk_event(
            "reddit:t3_phase4_03b",
            title=BASE_TITLE,
            text=BASE_TEXT,
            ticker="AAPL",
            created_at=now + 60,
        ),

        # 5) KEEP — same content, DIFFERENT bucket
        mk_event(
            "reddit:t3_phase4_04b",
            title=BASE_TITLE,
            text=BASE_TEXT,
            ticker="TSLA",
            created_at=now + 3700,  # next hour bucket
        ),

        # 6) KEEP — different content
        mk_event(
            "reddit:t3_phase4_05b",
            title="Different content",
            text="Completely different thought on NVDA today.",
            ticker="NVDA",
            created_at=now,
        ),
    ]


def main():
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=5,
    )

    events = build_events()
    print(f"Publishing {len(events)} Phase-4 dedup test events")

    for e in events:
        producer.send(
            RAW_TOPIC,
            key=e["eventId"],
            value=e,
            headers=[
                ("source", b"REDDIT"),
                ("entityType", b"POST"),
            ],
        ).get(timeout=10)

        print(f"sent {e['eventId']}")

    producer.flush()
    producer.close()

    print("\nEXPECTED RESULTS")
    print("CLEANED:")
    print(" - reddit:t3_phase4_01b")
    print(" - reddit:t3_phase4_03b")
    print(" - reddit:t3_phase4_04b")
    print(" - reddit:t3_phase4_05b")
    print("DROPPED:")
    print(" - reddit:t3_phase4_01b (EXACT_DUP_EVENT_ID)")
    print(" - reddit:t3_phase4_02b (EXACT_DUP_CONTENT)")


if __name__ == "__main__":
    main()
