"""
Seed 20 test IngestorEvent messages into Kafka.

- Sends to: sentrix.ingestor.events  (your raw topic)
- Mix:
  - ~12 should KEEP  -> go to sentrix.filter-service-a.cleaned
  - ~8 should DROP   -> go to sentrix.filter-service-a.dropped
    (based on your FilteringPipelineImpl hard checks)

Requires:
  pip install kafka-python
"""

import json
import time
from kafka import KafkaProducer

BOOTSTRAP = "localhost:9092"

RAW_TOPIC = "sentrix.ingestor.events"


def now_epoch() -> int:
    return int(time.time())


def mk_base_event(i: int) -> dict:
    # A "good" baseline event (should KEEP)
    # Your pipeline requires:
    # - event != null
    # - (eventId OR dedupKey) present
    # - source != null
    # - entityType != null
    # - combinedText(title+text) not blank
    return {
        "author": f"test_user_{i}",
        "capture": {
            "query": "$TSLA",
            "sort": "new",
            "timeWindow": "week",
            "fetchedFrom": "r/stocks",
            "searchMode": "search",
        },
        "community": "stocks",
        "contentUrl": f"https://example.com/post/{i}",
        "createdAtUtc": now_epoch() - 3600,
        "dedupKey": f"reddit:t3_seed_{i}",
        "entityType": "POST",
        "eventId": f"reddit:t3_seed_{i}",
        "eventVersion": 1,
        "ingestedAtUtc": now_epoch(),
        "lang": None,
        "metrics": {
            "likeCount": 0,
            "replyCount": None,
            "shareCount": None,
            "viewCount": None,
        },
        "platform": {
            "id": f"seed_{i}",
            "platformType": None,
            "fullName": f"t3_seed_{i}",
            "permalink": f"/r/stocks/comments/seed_{i}/",
            "rawUrl": f"https://example.com/post/{i}",
        },
        "source": "REDDIT",
        "text": f"Test body text for event {i}. Some market chatter here.",
        "thread": None,
        "ticker": "TSLA",
        "title": f"Seed event {i}: TSLA discussion",
    }


def build_events() -> list[tuple[str, dict, dict]]:
    """
    Returns list of (key, event_json, headers_dict)

    headers_dict -> will be converted to Kafka headers.
    Your handler reads headers: "source", "entityType"
    """
    events: list[tuple[str, dict, dict]] = []

    # ---- 12 KEEP messages ----
    for i in range(1, 13):
        e = mk_base_event(i)
        key = e["eventId"]
        headers = {"source": "REDDIT", "entityType": "POST"}
        events.append((key, e, headers))

    # ---- 8 DROP messages ----
    # 13) EMPTY_TEXT (title blank, text blank) => DROP
    e13 = mk_base_event(13)
    e13["title"] = "   "
    e13["text"] = ""
    events.append((e13["eventId"], e13, {"source": "REDDIT", "entityType": "POST"}))

    # 14) MISSING_REQUIRED_FIELD (no eventId and no dedupKey) => DROP
    e14 = mk_base_event(14)
    e14["eventId"] = "   "
    e14["dedupKey"] = None
    events.append(("seed_missing_ids_14", e14, {"source": "REDDIT", "entityType": "POST"}))

    # 15) INVALID_SOURCE (source null) => DROP
    e15 = mk_base_event(15)
    e15["source"] = None
    events.append((e15["eventId"], e15, {"source": None, "entityType": "POST"}))

    # 16) INVALID_EVENT_TYPE (entityType null) => DROP
    e16 = mk_base_event(16)
    e16["entityType"] = None
    events.append((e16["eventId"], e16, {"source": "REDDIT", "entityType": None}))

    # 17) RAW_PARSE_FAIL => send invalid JSON bytes
    # (Your handler catches parse fail and publishes DROP with RAW_PARSE_FAIL)
    # We'll represent this as a special marker (value will be raw bytes later)
    events.append(
        ("seed_raw_parse_fail_17", {"__RAW_BYTES__": b"{not valid json"}, {"source": "REDDIT", "entityType": "POST"}))

    # 18) EMPTY_TEXT (title ok, text null/blank) => DROP
    e18 = mk_base_event(18)
    e18["text"] = "   "
    events.append((e18["eventId"], e18, {"source": "REDDIT", "entityType": "POST"}))

    # 19) INVALID_SOURCE (source missing entirely) => DROP
    e19 = mk_base_event(19)
    del e19["source"]
    events.append((e19["eventId"], e19, {"source": "REDDIT", "entityType": "POST"}))

    # 20) INVALID_EVENT_TYPE (entityType missing entirely) => DROP
    e20 = mk_base_event(20)
    del e20["entityType"]
    events.append((e20["eventId"], e20, {"source": "REDDIT", "entityType": "POST"}))

    return events


def to_headers(headers: dict) -> list[tuple[str, bytes]]:
    out = []
    for k, v in headers.items():
        if v is None:
            continue
        out.append((k, str(v).encode("utf-8")))
    return out


def main():
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: v if isinstance(v, (bytes, bytearray)) else json.dumps(v).encode("utf-8"),
        linger_ms=10,
    )

    events = build_events()

    print(f"Sending {len(events)} events to {RAW_TOPIC} on {BOOTSTRAP} ...")
    for idx, (key, payload, headers_dict) in enumerate(events, start=1):
        if isinstance(payload, dict) and "__RAW_BYTES__" in payload:
            value = payload["__RAW_BYTES__"]
        else:
            value = payload

        fut = producer.send(
            RAW_TOPIC,
            key=key,
            value=value,
            headers=to_headers(headers_dict),
        )
        md = fut.get(timeout=10)
        print(f"{idx:02d}) sent key={key} -> {md.topic} p={md.partition} off={md.offset}")

    producer.flush()
    producer.close()
    print("Done.")


if __name__ == "__main__":
    main()
