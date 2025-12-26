"""

Publishes 20 IngestorEvent JSON messages into RAW topic so the events:

RAW (sentrix.ingestor.events)
  -> Filtering Service A/B
     -> CLEANED (sentrix.filter-service-a.cleaned)
        -> Sentiment Service
           -> MongoDB hourly upserts + signal placeholder upserts (later, after grace)

This uses the exact 20 tickers provided (including "BRK.B").

Prereq:
  pip install kafka-python

Run:
  python seed_sentiment_e2e_20_tickers.py
"""

import json
import time
import uuid
from typing import List

from kafka import KafkaProducer

BOOTSTRAP = "localhost:9092"
RAW_TOPIC = "sentrix.ingestor.events"

SOURCE = "REDDIT"
ENTITY_TYPE = "POST"
COMMUNITY = "stocks"
AUTHOR = "seed_user"


def now_epoch() -> int:
    return int(time.time())


def mk_event(
    *,
    event_id: str,
    ticker: str,
    created_at_utc: int,
    title: str,
    text: str,
) -> dict:
    return {
        "eventVersion": 1,
        "source": SOURCE,
        "entityType": ENTITY_TYPE,
        "eventId": event_id,
        "dedupKey": event_id,
        "createdAtUtc": int(created_at_utc),
        "ingestedAtUtc": int(created_at_utc),
        "ticker": ticker,
        "community": COMMUNITY,
        "author": AUTHOR,
        "title": title,
        "text": text,
        "contentUrl": f"https://reddit.com/{event_id}",
        "platform": {
            "id": event_id.split(":")[-1],
            "fullName": event_id,
            "permalink": f"/r/{COMMUNITY}/comments/{event_id}",
            "rawUrl": f"https://reddit.com/{event_id}",
        },
        "thread": None,
        "metrics": {"likeCount": 1, "commentCount": 0},
        "capture": {"query": f"${ticker}", "fetchedFrom": f"r/{COMMUNITY}"},
        "lang": None,
    }


def _long_text_for_ticker(ticker: str, seed: str) -> str:
    # Long enough to pass Phase 3 min-text-len and not trigger Phase 5.
    # No URLs, no emoji spam, no repeated-char abuse, no multi-ticker spam.
    # Includes the ticker (without $) in case any downstream logic looks for it in text.
    return (
        f"Tracking {ticker} into the next session with a cautious plan. "
        f"Price action has been choppy but the higher time frame support looks stable. "
        f"My focus is on whether buyers keep defending dips and whether volume improves. "
        f"I am watching for confirmation from broader market direction and sector strength. "
        f"This note is for research context only and is not financial advice. "
        f"Seed={seed}."
    )


def build_events() -> List[dict]:
    ts = now_epoch()

    tickers = [
        "TSLA",
        "AAPL",
        "MSFT",
        "NVDA",
        "AMZN",
        "GOOGL",
        "META",
        "BRK.B",
        "JPM",
        "V",
        "MA",
        "WMT",
        "LLY",
        "XOM",
        "JNJ",
        "ORCL",
        "AVGO",
        "COST",
        "NKE",
        "PFE",
    ]

    run_id = uuid.uuid4().hex[:8]
    events: List[dict] = []

    # Keep all events within the same hour, but spread by a couple seconds.
    for i, ticker in enumerate(tickers, start=1):
        created_at = ts - (len(tickers) - i) * 2  # last ~40 seconds
        event_id = f"seed:e2e:{run_id}:{i:02d}:{ticker.lower().replace('.', '-')}"
        title = f"E2E seed {i:02d} {ticker}"
        text = _long_text_for_ticker(ticker, seed=f"{run_id}-{i:02d}")

        events.append(
            mk_event(
                event_id=event_id,
                ticker=ticker,
                created_at_utc=created_at,
                title=title,
                text=text,
            )
        )

    return events


def main() -> None:
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=5,
    )

    events = build_events()
    print(f"Publishing {len(events)} E2E events to RAW topic={RAW_TOPIC}")

    for e in events:
        producer.send(
            RAW_TOPIC,
            key=e["eventId"],
            value=e,
            headers=[
                ("source", SOURCE.encode("utf-8")),
                ("entityType", ENTITY_TYPE.encode("utf-8")),
            ],
        ).get(timeout=10)

        print(
            f"sent eventId={e['eventId']} ticker={e['ticker']} createdAtUtc={e['createdAtUtc']}"
        )

    producer.flush()
    producer.close()

    print("\nExpected:")
    print(
        "1) Filtering Service A: KEEP envelopes on sentrix.filter-service-a.cleaned for all 20 events."
    )
    print("2) Sentiment Service: hourly upserts for each (ticker, hourStartUtc).")
    print(
        "3) Signal collection: placeholder updates only after eligible hour passes grace."
    )


if __name__ == "__main__":
    main()
    main()
