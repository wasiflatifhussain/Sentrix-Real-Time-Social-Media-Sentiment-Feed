"""
seed_phase5_feature_checks.py

Publishes test IngestorEvent JSON messages into RAW topic to verify Phase 5
(event-feature-checks) heuristic drops.

Guarantees:
- Passes Phase 1 (required fields present)
- Passes Phase 2 (normalizer sees raw URLs -> <URL>, cashtags extracted, etc.)
- Passes Phase 3 (min-text-len >= 10, age <= 7 days)
- Avoids Phase 4 dedup collisions by using unique eventId/dedupKey and unique content.

Covers Phase 5 DROP reasons:
- URL_SPAM_EXCESSIVE
- EXCESSIVE_EMOJI_SIGNAL
- REPEATED_CHAR_SIGNAL
- MULTI_TICKER_SPAM_SIGNAL

Also includes KEEP controls near thresholds to ensure we only drop slam-dunks.

Prereq:
  pip install kafka-python

Run:
  python seed_phase5_feature_checks.py

Then inspect CLEANED vs DROPPED topics (kafdrop / console consumer).

Config assumed (from your yml):
- url-spam: hard=6, shortText=3 (<=8 words)
- emoji: hard=20, shortText=10 (<=6 words)
- repeat-char: hard-run-len=12
- cashtag: hard=12, shortText=6 (<=12 words)
"""

import json
import time
from kafka import KafkaProducer

BOOTSTRAP = "localhost:9092"
RAW_TOPIC = "sentrix.ingestor.events"


def now_epoch() -> int:
    return int(time.time())


def mk_event(event_id: str, *, title: str, text: str, ticker: str, created_at: int):
    # Keep structure consistent with your Phase4 seeder so deserialization stays stable.
    return {
        "eventVersion": 1,
        "source": "REDDIT",
        "entityType": "POST",
        "eventId": event_id,
        "dedupKey": event_id,  # unique
        "createdAtUtc": created_at,
        "ingestedAtUtc": created_at,
        "ticker": ticker,
        "community": "stocks",
        "author": "phase5_user",
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

    # Keep: normal baseline (1 URL, normal words)
    keep_baseline = mk_event(
        "reddit:t3_phase5_keep_01",
        title="Phase5 baseline keep",
        text="TSLA looks strong here. Earnings were solid. https://example.com",
        ticker="TSLA",
        created_at=now,
    )

    # ---------- URL SPAM ----------
    # DROP: hard-drop-count=6 URLs
    drop_url_hard = mk_event(
        "reddit:t3_phase5_drop_url_hard",
        title="URL spam hard",
        text=(
            "Check links: "
            "https://a.com https://b.com https://c.com https://d.com https://e.com https://f.com "
            "This should drop."
        ),
        ticker="AAPL",
        created_at=now + 1,
    )

    # DROP: short-text-drop-count=3 URLs AND <=8 words
    # Word count here should be small: "Wow" (1) + three URLs (3 tokens) => 4 words (<=8)
    drop_url_short = mk_event(
        "reddit:t3_phase5_drop_url_short",
        title="URL spam short text",
        text="Wow https://a.com https://b.com https://c.com",
        ticker="MSFT",
        created_at=now + 2,
    )

    # KEEP control: 3 URLs but >8 words (should NOT trigger short-text rule)
    keep_url_3_long = mk_event(
        "reddit:t3_phase5_keep_url_3_long",
        title="3 urls but meaningful text",
        text=(
            "Here are three sources for the claim with context and explanation "
            "https://a.com https://b.com https://c.com"
        ),
        ticker="GOOG",
        created_at=now + 3,
    )

    # ---------- EMOJI ----------
    # DROP: hard-drop-count=20 emojis (we include some normal words too)
    drop_emoji_hard = mk_event(
        "reddit:t3_phase5_drop_emoji_hard",
        title="Emoji hard spam",
        text="This is insane " + ("😂" * 20),
        ticker="NVDA",
        created_at=now + 4,
    )

    # DROP: short-text-drop-count=10 emojis AND <=6 words
    # words: "BUY" (1) "NOW" (2) + emojis appended to same token => still <=6
    drop_emoji_short = mk_event(
        "reddit:t3_phase5_drop_emoji_short",
        title="Emoji short spam",
        text="BUY NOW " + ("🚀" * 10),
        ticker="AMD",
        created_at=now + 5,
    )

    # KEEP control: 10 emojis but >6 words (should NOT trigger short-text rule)
    keep_emoji_10_long = mk_event(
        "reddit:t3_phase5_keep_emoji_10_long",
        title="Emoji but long text",
        text="I am genuinely excited about the earnings call today " + ("🚀" * 10),
        ticker="META",
        created_at=now + 6,
    )

    # ---------- REPEATED CHAR ----------
    # DROP: hard-run-len=12 repeated characters
    drop_repeat_hard = mk_event(
        "reddit:t3_phase5_drop_repeat_hard",
        title="Repeated char spam",
        text="This is so good!!!!!!!!!!!! wow that was wild",  # 12 '!'s
        ticker="NFLX",
        created_at=now + 7,
    )

    # KEEP control: 11 repeated chars (below threshold)
    keep_repeat_11 = mk_event(
        "reddit:t3_phase5_keep_repeat_11",
        title="Repeated char below threshold",
        text="This is so good!!!!!!!!!!! wow",  # 11 '!'s
        ticker="ORCL",
        created_at=now + 8,
    )

    # ---------- CASHTAG ----------
    # DROP: hard-drop-count=12 UNIQUE cashtags (your extractor uses extractUnique)
    cashtags_12 = " ".join(
        [
            "$AAPL", "$MSFT", "$TSLA", "$NVDA", "$AMD", "$META",
            "$GOOG", "$AMZN", "$NFLX", "$ORCL", "$INTC", "$UBER"
        ]
    )
    drop_cashtag_hard = mk_event(
        "reddit:t3_phase5_drop_cashtag_hard",
        title="Many cashtags hard",
        text=f"Tickers: {cashtags_12} and that's the post.",
        ticker="TSLA",
        created_at=now + 9,
    )

    # DROP: short-text-drop-count=6 UNIQUE cashtags AND <=12 words
    # Keep it short: "Picks:" (1) + 6 tickers (6 tokens) => 7 words (<=12)
    cashtags_6 = " ".join(["$AAPL", "$MSFT", "$TSLA", "$NVDA", "$AMD", "$META"])
    drop_cashtag_short = mk_event(
        "reddit:t3_phase5_drop_cashtag_short",
        title="Many cashtags short",
        text=f"Picks: {cashtags_6}",
        ticker="AAPL",
        created_at=now + 10,
    )

    # KEEP control: 6 cashtags but >12 words (should NOT trigger short-text rule)
    keep_cashtag_6_long = mk_event(
        "reddit:t3_phase5_keep_cashtag_6_long",
        title="Cashtags but long text",
        text=(
            f"I'm watching these names for different reasons across sectors today: "
            f"{cashtags_6} and will add notes after the open."
        ),
        ticker="MSFT",
        created_at=now + 11,
    )

    return [
        keep_baseline,
        drop_url_hard,
        drop_url_short,
        keep_url_3_long,
        drop_emoji_hard,
        drop_emoji_short,
        keep_emoji_10_long,
        drop_repeat_hard,
        keep_repeat_11,
        drop_cashtag_hard,
        drop_cashtag_short,
        keep_cashtag_6_long,
    ]


def main():
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=5,
    )

    events = build_events()
    print(f"Publishing {len(events)} Phase-5 feature-check test events")

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

    print("\nEXPECTED RESULTS (Phase 5)")
    print("CLEANED (KEEP):")
    print(" - reddit:t3_phase5_keep_01")
    print(" - reddit:t3_phase5_keep_url_3_long")
    print(" - reddit:t3_phase5_keep_emoji_10_long")
    print(" - reddit:t3_phase5_keep_repeat_11")
    print(" - reddit:t3_phase5_keep_cashtag_6_long")
    print("\nDROPPED (by Phase 5):")
    print(" - reddit:t3_phase5_drop_url_hard (URL_SPAM_EXCESSIVE)")
    print(" - reddit:t3_phase5_drop_url_short (URL_SPAM_EXCESSIVE)")
    print(" - reddit:t3_phase5_drop_emoji_hard (EXCESSIVE_EMOJI_SIGNAL)")
    print(" - reddit:t3_phase5_drop_emoji_short (EXCESSIVE_EMOJI_SIGNAL)")
    print(" - reddit:t3_phase5_drop_repeat_hard (REPEATED_CHAR_SIGNAL)")
    print(" - reddit:t3_phase5_drop_cashtag_hard (MULTI_TICKER_SPAM_SIGNAL)")
    print(" - reddit:t3_phase5_drop_cashtag_short (MULTI_TICKER_SPAM_SIGNAL)")


if __name__ == "__main__":
    main()
