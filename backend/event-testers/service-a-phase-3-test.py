"""
seed_phase3_events.py

Publishes test IngestorEvent JSON messages into RAW topic so you can verify Phase 3 Validator:
- TOO_SHORT_TEXT (min-text-len)
- TOO_OLD (max-event-age-days)
- OVERSIZE_TRUNCATED (drop-on-truncate=true)
- EMPTY_TEXT (blank after normalization/cleanup)

Prereq:
  pip install kafka-python

Run:
  python seed_phase3_events.py

Before running, set your Service A config for Phase 3 testing, e.g.

app:
  validation:
    min-text-len: 12
    max-event-age-days: 7
    drop-on-truncate: true

app:
  text:
    max-len: 200   # set low so truncation test is easy (optional)

Then inspect:
- sentrix.filter-service-a.cleaned  (KEEPs)
- sentrix.filter-service-a.dropped  (DROPs with filterReason)
"""

import json
import time
from kafka import KafkaProducer

BOOTSTRAP = "localhost:9092"
RAW_TOPIC = "sentrix.ingestor.events"


def now_epoch() -> int:
    return int(time.time())


def mk_event(
        i: int,
        title: str,
        text: str,
        ticker: str,
        *,
        created_at_utc: int | None = None,
        entity_type: str = "POST",
        source: str = "REDDIT",
        like_count: int = 0,
        reply_count=None,
):
    eid = f"reddit:t3_phase3_{i:02d}"
    return {
        "author": f"phase3_user_{i}",
        "capture": {
            "query": f"${ticker}",
            "sort": "new",
            "timeWindow": "week",
            "fetchedFrom": "r/stocks",
            "searchMode": "search",
        },
        "community": "stocks",
        "contentUrl": f"https://www.reddit.com/r/stocks/comments/phase3_{i:02d}/",
        "createdAtUtc": created_at_utc if created_at_utc is not None else (now_epoch() - 120),
        "dedupKey": eid,
        "entityType": entity_type,
        "eventId": eid,
        "eventVersion": 1,
        "ingestedAtUtc": now_epoch(),
        "lang": None,
        "metrics": {"likeCount": like_count, "replyCount": reply_count, "shareCount": None, "viewCount": None},
        "platform": {
            "id": f"phase3_{i:02d}",
            "platformType": None,
            "fullName": f"t3_phase3_{i:02d}",
            "permalink": f"/r/stocks/comments/phase3_{i:02d}/",
            "rawUrl": f"https://www.reddit.com/r/stocks/comments/phase3_{i:02d}/",
        },
        "source": source,
        "text": text,
        "thread": None,
        "ticker": ticker,
        "title": title,
    }


def to_headers(d: dict):
    out = []
    for k, v in d.items():
        if v is None:
            continue
        out.append((k, str(v).encode("utf-8")))
    return out


def build_events():
    """
    Expected outcomes assume:
      min-text-len = 12
      max-event-age-days = 7
      drop-on-truncate = true
      text max-len small enough to truncate (optional)
    """

    events = []

    # 1) KEEP: normal post with enough text
    events.append(
        mk_event(
            1,
            title="Phase3 KEEP $TSLA",
            text="I think $tsla looks strong here. https://example.com #stocks @user",
            ticker="TSLA",
        )
    )

    # 2) DROP: too short (after normalization)
    # If min-text-len=12, this should fail.
    events.append(
        mk_event(
            2,
            title=None,  # comment-like
            text="ok $tsla",  # short
            ticker="TSLA",
            entity_type="COMMENT",
        )
    )

    # 3) DROP: empty-ish (whitespace only)
    events.append(
        mk_event(
            3,
            title="   ",
            text="   \n\t\r   ",
            ticker="AAPL",
        )
    )

    # 4) DROP: too old (createdAtUtc far in the past)
    # If max-event-age-days=7, set 10 days old.
    ten_days_sec = 10 * 24 * 3600
    events.append(
        mk_event(
            4,
            title="Old post $NVDA",
            text="This should drop because it's too old.",
            ticker="NVDA",
            created_at_utc=now_epoch() - ten_days_sec,
        )
    )

    # 5) KEEP: borderline but still >= 12 chars (useful for confirming threshold)
    events.append(
        mk_event(
            5,
            title=None,
            text="Overreaction imo",  # 16 chars-ish, should pass min len
            ticker="MSFT",
            entity_type="COMMENT",
        )
    )

    # 6) DROP: truncation policy (requires app.text.max-len low + drop-on-truncate=true)
    # Set app.text.max-len=200 (or similar) in Service A to guarantee truncation.
    long_text = ("word " * 500) + " https://example.com " + ("A" * 500)
    events.append(
        mk_event(
            6,
            title="Truncation test $TSLA",
            text=long_text,
            ticker="TSLA",
        )
    )

    # 7) KEEP: lots of URLs but still valid (Phase 5 will kill URL spam later)
    # Here it should KEEP unless your validator also checks urlCount (it doesn't).
    events.append(
        mk_event(
            7,
            title="Many URLs but should KEEP in Phase3",
            text="See https://a.com https://b.com https://c.com and $msft",
            ticker="MSFT",
        )
    )

    # 8) DROP: missing ids (Phase1 check will drop BEFORE validator)
    # Good to confirm earlier guard still works.
    e = mk_event(
        8,
        title="Bad IDs",
        text="Has text but missing eventId+dedupKey; should drop Phase1 MISSING_REQUIRED_FIELD",
        ticker="TSLA",
    )
    e["eventId"] = ""
    e["dedupKey"] = ""
    events.append(e)

    return events


def main():
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=10,
    )

    events = build_events()
    print(f"Publishing {len(events)} Phase-3 test events -> {RAW_TOPIC} ({BOOTSTRAP})")

    for e in events:
        key = e.get("eventId") or f"phase3_noid_{int(time.time() * 1000)}"
        headers = {"source": e.get("source"), "entityType": e.get("entityType")}
        md = producer.send(RAW_TOPIC, key=key, value=e, headers=to_headers(headers)).get(timeout=10)
        print(f"sent key={key} -> p={md.partition} off={md.offset}")

    producer.flush()
    producer.close()

    print("\nDone.\n")
    print("Now verify in Kafka:")
    print("- CLEANED topic should contain: events 1, 5, 7 (and maybe 6 if you didn't enable truncation drop)")
    print("- DROPPED topic should contain:")
    print("    event 2 -> TOO_SHORT_TEXT")
    print("    event 3 -> EMPTY_TEXT")
    print("    event 4 -> TOO_OLD   (only if max-event-age-days > 0)")
    print("    event 8 -> MISSING_REQUIRED_FIELD (Phase1 guard)")


if __name__ == "__main__":
    main()
