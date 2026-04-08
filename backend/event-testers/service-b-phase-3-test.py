"""
seed_filter_b_phase3_events.py

Publishes curated Filter-A-cleaned envelopes directly into:
  sentrix.filter-service-a.cleaned

Use this to validate Filtering Service B Phase 3 (ticker relevance stage):
- happy path KEEP
- low relevance penalties/reasons
- extreme irrelevance REJECT
- unknown ticker profile REJECT
- invalid payload -> INVALID_INPUT handling in service B

Prereq:
  pip install kafka-python

Run:
  python backend/event-testers/service-b-phase-3-test.py
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass

from kafka import KafkaProducer

BOOTSTRAP = "localhost:9092"
FILTER_A_CLEANED_TOPIC = "sentrix.filter-service-a.cleaned"


@dataclass(frozen=True)
class SeedCase:
    case_id: str
    ticker: str
    title: str
    body: str
    expected: str
    force_invalid_payload: bool = False


def now_epoch() -> int:
    return int(time.time())


def _mk_cleaned_envelope(run_id: str, index: int, case: SeedCase) -> dict:
    event_id = f"fbp3:{run_id}:{index:02d}:{case.case_id}"
    title = case.title.strip()
    body = case.body.strip()
    text_normalized = f"{title}\n{body}" if title else body

    return {
        "ingestorEvent": {
            "author": "filter-b-phase3-tester",
            "capture": {
                "query": f"${case.ticker}",
                "sort": "new",
                "timeWindow": "week",
                "fetchedFrom": "r/stocks",
                "searchMode": "search",
            },
            "community": "stocks",
            "contentUrl": f"https://example.com/{event_id}",
            "createdAtUtc": now_epoch() - 30,
            "dedupKey": event_id,
            "entityType": "POST",
            "eventId": event_id,
            "eventVersion": 1,
            "ingestedAtUtc": now_epoch(),
            "lang": None,
            "metrics": {"likeCount": 1, "commentCount": 0},
            "platform": {
                "id": event_id.split(":")[-1],
                "platformType": None,
                "fullName": event_id,
                "permalink": f"/r/stocks/comments/{event_id}",
                "rawUrl": f"https://example.com/{event_id}",
            },
            "source": "REDDIT",
            "text": body,
            "thread": None,
            "ticker": case.ticker,
            "title": title,
        },
        "filterMeta": {
            "filterStage": "service_a",
            "decision": "KEEP",
            "filterReason": None,
            "processedAtUtc": now_epoch(),
            "tags": None,
            "signals": None,
        },
        "textView": {
            "textNormalized": text_normalized,
            "wasTruncated": False,
            "originalTextLength": len(text_normalized),
        },
        "eventFeatures": {
            "wordCount": len(text_normalized.split()),
            "charCount": len(text_normalized),
            "urlCount": 0,
            "hashtagCount": 0,
            "extractedHashtags": [],
            "mentionCount": 0,
            "extractedMentions": [],
            "cashTagCount": 0,
            "extractedCashTags": [],
            "capsRatio": 0.0,
            "emojiCount": 0,
            "maxRepeatedCharCount": 2,
        },
    }


def build_cases() -> list[SeedCase]:
    return [
        SeedCase(
            case_id="happy_strong_tsla_v2",
            ticker="TSLA",
            title="Tesla delivery growth and margin outlook",
            body=(
                "Tesla shares moved after TSLA reported stronger deliveries and updated "
                "margin outlook. Traders are discussing earnings quality, valuation, "
                "and forward guidance for the stock."
            ),
            expected="KEEP with strong_relevance signal (high confidence)",
        ),
        SeedCase(
            case_id="likely_low_relevance_v2",
            ticker="TSLA",
            title="Lifestyle post with one ticker mention",
            body=(
                "Quick daily update: gym, coffee, and errands done. TSLA appeared once in "
                "a chat screenshot, but this is mostly personal life content, not business "
                "or investing analysis."
            ),
            expected=(
                "Usually KEEP with LOW_TICKER_RELEVANCE or REJECT if similarity is very low "
                "(model-dependent)"
            ),
        ),
        SeedCase(
            case_id="extreme_irrelevant_v2",
            ticker="TSLA",
            title="Recipe and cooking notes",
            body=(
                "Prepared pasta with tomato sauce and herbs, then planned meals for the week. "
                "This post is about food and kitchen prep only, without any company, stock, "
                "or financial context."
            ),
            expected="REJECT with EXTREME_LOW_TICKER_RELEVANCE (high confidence)",
        ),
        SeedCase(
            case_id="unknown_ticker_profile_v2",
            ticker="ZZZZ",
            title="Unknown ticker profile check",
            body="Discussing ZZZZ momentum and possible breakout, but ticker profile is unavailable.",
            expected="REJECT with UNKNOWN_TICKER_PROFILE (deterministic)",
        ),
        SeedCase(
            case_id="invalid_payload_v2",
            ticker="TSLA",
            title="Malformed cleaned envelope",
            body="Payload intentionally removes textView to trigger INVALID_INPUT path.",
            expected="REJECT with INVALID_INPUT (deterministic)",
            force_invalid_payload=True,
        ),
    ]


def main() -> None:
    run_id = uuid.uuid4().hex[:8]
    cases = build_cases()

    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=5,
    )

    print(f"Run ID: {run_id}")
    print(f"Sending {len(cases)} cases -> {FILTER_A_CLEANED_TOPIC} @ {BOOTSTRAP}\n")

    for idx, case in enumerate(cases, start=1):
        payload = _mk_cleaned_envelope(run_id, idx, case)
        if case.force_invalid_payload:
            payload.pop("textView", None)

        event_id = payload["ingestorEvent"]["eventId"]
        headers = [
            ("decision", b"KEEP"),
            ("entityType", b"POST"),
            ("source", b"REDDIT"),
        ]

        md = producer.send(
            FILTER_A_CLEANED_TOPIC,
            key=event_id,
            value=payload,
            headers=headers,
        ).get(timeout=10)

        print(
            f"{idx:02d}) sent eventId={event_id} ticker={case.ticker} -> "
            f"p={md.partition} off={md.offset}"
        )
        print(f"    expected: {case.expected}")

    producer.flush()
    producer.close()

    print("\nDone.")
    print("Next: run the listener tester and filter by this runId to verify output decisions.")
    print(f"runId={run_id}")


if __name__ == "__main__":
    main()
