"""
seed_phase6_near_dup.py

Publishes test IngestorEvent JSON messages into RAW topic to verify Phase 6
(near-duplicate SimHash tagging).

Guarantees:
- Passes Phase 1 (required fields present)
- Passes Phase 2/3 (text long enough, recent timestamps)
- Avoids Phase 4 collisions via unique eventId/dedupKey
- Avoids Phase 5 triggers (no URL spam / emoji spam / cashtag spam / repeated chars)

What it tests:
1) A "wave" of near-duplicate posts for the same ticker within the same bucket
   -> expect NEAR_DUP_WAVE tag on later ones (when matchCount >= min-matches).
2) A control: same ticker but very different text -> should NOT be tagged.
3) A short-text control: below min-words -> should NOT be checked/tagged.
4) Optional: bucket-boundary test (relies on check-prev-bucket=true).

Prereq:
  pip install kafka-python

Run:
  python seed_phase6_near_dup.py

Then inspect CLEANED topic and confirm:
- Some events include filterMeta.tags=["NEAR_DUP_WAVE"]
- filterMeta.signals has nearDupMatchCount/minHamming/etc.
"""

import json
import time
from kafka import KafkaProducer

BOOTSTRAP = "localhost:9092"
RAW_TOPIC = "sentrix.ingestor.events"


def now_epoch() -> int:
    return int(time.time())


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
        "author": "phase6_user",
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


def base_near_dup_text():
    # Make it long enough to exceed your minWords=30 comfortably.
    return (
        "Watching TSLA into the next session. "
        "Price is holding above a key support zone and volume is steady. "
        "The main idea is that buyers are defending dips and sellers are not accelerating. "
        "If the market stays risk-on, I expect continuation with a cautious stop below support. "
        "Not financial advice; sharing my reasoning and what I am watching for confirmation."
    )


def variant(text: str, *, tweak: str):
    # Small edits to keep near-dup similarity high (copy/paste campaign style)
    return text.replace("key support zone", tweak)


def very_different_text():
    return (
        "Completely different discussion: I am comparing EV supply chains and battery costs. "
        "This is not about price action. I am focused on manufacturing constraints, margins, and "
        "long-term demand projections across regions. I will revisit valuation after the next report."
    )


def short_text_under_min_words():
    # Intentionally too short to meet minWords=30
    return "TSLA looks interesting today. Holding support and watching volume."


def build_events():
    now = now_epoch()

    # --- Wave events (same ticker/source, very similar text) ---
    t0 = base_near_dup_text()

    # 1) First one should NOT be tagged (no prior matches)
    e1 = mk_event(
        "reddit:t3_phase6_wave_01",
        title="Phase6 wave 01",
        text=t0,
        ticker="TSLA",
        created_at=now,
    )

    # 2) Second one may or may not be tagged depending on minMatches
    e2 = mk_event(
        "reddit:t3_phase6_wave_02",
        title="Phase6 wave 02",
        text=variant(t0, tweak="important support area"),
        ticker="TSLA",
        created_at=now + 5,
    )

    # 3) Third one: with minMatches=3, still might not tag yet depending on your counting semantics.
    # Your current code counts matches among *existing* fingerprints only; so wave often triggers from #4 onward.
    e3 = mk_event(
        "reddit:t3_phase6_wave_03",
        title="Phase6 wave 03",
        text=variant(t0, tweak="major demand zone"),
        ticker="TSLA",
        created_at=now + 10,
    )

    # 4) Fourth one: should be tagged if the earlier ones are within maxHamming and stored in Redis
    e4 = mk_event(
        "reddit:t3_phase6_wave_04",
        title="Phase6 wave 04",
        text=variant(t0, tweak="strong support region"),
        ticker="TSLA",
        created_at=now + 15,
    )

    # 5) Fifth one: should also be tagged
    e5 = mk_event(
        "reddit:t3_phase6_wave_05",
        title="Phase6 wave 05",
        text=variant(t0, tweak="well-defined support band"),
        ticker="TSLA",
        created_at=now + 20,
    )

    # --- Control: same ticker but very different text -> should NOT be tagged ---
    c1 = mk_event(
        "reddit:t3_phase6_control_diff_01",
        title="Phase6 control different text",
        text=very_different_text(),
        ticker="TSLA",
        created_at=now + 25,
    )

    # --- Control: short text under minWords -> should not even run Phase 6 ---
    c2 = mk_event(
        "reddit:t3_phase6_control_short_01",
        title="Phase6 control short text",
        text=short_text_under_min_words(),
        ticker="TSLA",
        created_at=now + 30,
    )

    # --- Optional boundary test (only meaningful if you want to observe check-prev-bucket) ---
    # We try to place events near a 15-min bucket boundary. This isn't perfect, but should help.
    # bucketSeconds = 900
    bucket = now // 900
    boundary = (bucket + 1) * 900  # next bucket start
    b1_time = boundary - 2
    b2_time = boundary + 2

    b1 = mk_event(
        "reddit:t3_phase6_boundary_01",
        title="Phase6 boundary 01",
        text=variant(t0, tweak="boundary support zone"),
        ticker="AAPL",
        created_at=b1_time,
    )

    b2 = mk_event(
        "reddit:t3_phase6_boundary_02",
        title="Phase6 boundary 02",
        text=variant(t0, tweak="boundary support area"),
        ticker="AAPL",
        created_at=b2_time,
    )

    return [e1, e2, e3, e4, e5, c1, c2, b1, b2]


def main():
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=5,
    )

    events = build_events()
    print(f"Publishing {len(events)} Phase-6 near-dup test events")

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
        print(f"sent {e['eventId']} createdAtUtc={e['createdAtUtc']} ticker={e['ticker']}")

    producer.flush()
    producer.close()

    print("\nEXPECTED RESULTS (Phase 6)")
    print("CLEANED (KEEP): all events should be KEEP (Phase 6 never DROPs).")
    print("\nTagged with NEAR_DUP_WAVE (likely):")
    print(" - reddit:t3_phase6_wave_04")
    print(" - reddit:t3_phase6_wave_05")
    print("\nNot tagged:")
    print(" - reddit:t3_phase6_wave_01 (no history)")
    print(" - reddit:t3_phase6_control_diff_01 (different text)")
    print(" - reddit:t3_phase6_control_short_01 (below minWords)")
    print("\nBoundary test (AAPL):")
    print(" - if check-prev-bucket=true, boundary_02 is more likely to tag if similarity is high and both are stored.")


if __name__ == "__main__":
    main()
