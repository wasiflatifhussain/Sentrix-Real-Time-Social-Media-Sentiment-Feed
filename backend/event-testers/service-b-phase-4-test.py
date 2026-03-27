"""
seed_filter_b_phase4_events.py

Publishes curated Filter-A-cleaned envelopes directly into:
  sentrix.filter-service-a.cleaned

Use this to validate Filtering Service B Phase 4 (Stage 2 manipulation/repetition):
- normal keep path
- cross-user repetition penalty
- dense similarity cluster penalty
- same-account repetition penalty
- burst-amplified repetition penalty
- burst-only benign path (no repetition -> no burst penalty)

Prereq:
  pip install kafka-python

Run:
  python backend/event-testers/service-b-phase-4-test.py
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
    author: str
    title: str
    body: str
    expected: str


def now_epoch() -> int:
    return int(time.time())


def _mk_cleaned_envelope(run_id: str, index: int, case: SeedCase) -> dict:
    event_id = f"fbp4:{run_id}:{index:02d}:{case.case_id}"
    title = case.title.strip()
    body = case.body.strip()
    text_normalized = f"{title}\n{body}" if title else body

    return {
        "ingestorEvent": {
            "author": case.author,
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
    repeated_tsla_text = (
        "TSLA option flow is heavy today after delivery guidance updates. "
        "Watching volume, open interest, and breakout levels for short-term momentum."
    )
    spammer_text = (
        "TSLA breakout alert based on repeated momentum setup and the same trigger levels. "
        "Posting this again to track the exact same setup."
    )

    return [
        SeedCase(
            case_id="baseline_keep_tsla_1",
            ticker="TSLA",
            author="phase4-base-a",
            title="Tesla margin discussion",
            body=(
                "TSLA investors are discussing margin pressure versus delivery growth before "
                "earnings, with focus on guidance and valuation."
            ),
            expected="KEEP (no Stage 2 repetition reasons)",
        ),
        SeedCase(
            case_id="cross_user_seed_1",
            ticker="TSLA",
            author="phase4-wave-a",
            title="TSLA flow watch",
            body=repeated_tsla_text,
            expected="Usually KEEP (seed for cross-user repetition)",
        ),
        SeedCase(
            case_id="cross_user_seed_2",
            ticker="TSLA",
            author="phase4-wave-b",
            title="TSLA flow watch",
            body=repeated_tsla_text,
            expected="Usually KEEP (second seed, may still be below threshold)",
        ),
        SeedCase(
            case_id="cross_user_trigger",
            ticker="TSLA",
            author="phase4-wave-c",
            title="TSLA flow watch",
            body=repeated_tsla_text,
            expected="KEEP/REJECT with CROSS_USER_REPETITION (score should drop)",
        ),
        SeedCase(
            case_id="cluster_trigger",
            ticker="TSLA",
            author="phase4-wave-d",
            title="TSLA flow watch",
            body=repeated_tsla_text,
            expected=(
                "KEEP/REJECT with CROSS_USER_REPETITION + DENSE_SIMILARITY_CLUSTER; "
                "burst amplification may also appear"
            ),
        ),
        SeedCase(
            case_id="same_account_seed_1",
            ticker="TSLA",
            author="phase4-spammer",
            title="Repeated TSLA setup",
            body=spammer_text,
            expected="Usually KEEP (seed for same-account repetition)",
        ),
        SeedCase(
            case_id="same_account_seed_2",
            ticker="TSLA",
            author="phase4-spammer",
            title="Repeated TSLA setup",
            body=spammer_text,
            expected="Usually KEEP (second seed for same-account repetition)",
        ),
        SeedCase(
            case_id="same_account_trigger",
            ticker="TSLA",
            author="phase4-spammer",
            title="Repeated TSLA setup",
            body=spammer_text,
            expected="KEEP/REJECT with SAME_ACCOUNT_REPETITION (possible burst amplification)",
        ),
        SeedCase(
            case_id="burst_only_benign_1",
            ticker="AAPL",
            author="phase4-benign-a",
            title="AAPL iPhone revenue mix",
            body="AAPL discussion on product mix, services growth, and margin trends.",
            expected="KEEP (no repetition reasons)",
        ),
        SeedCase(
            case_id="burst_only_benign_2",
            ticker="AAPL",
            author="phase4-benign-b",
            title="AAPL buyback and cash flow",
            body="AAPL cash return policy and buyback cadence analysis for long-term holders.",
            expected="KEEP (no repetition reasons)",
        ),
        SeedCase(
            case_id="burst_only_benign_3",
            ticker="AAPL",
            author="phase4-benign-c",
            title="AAPL valuation reset",
            body="AAPL multiple compression versus earnings durability in a higher-rate regime.",
            expected=(
                "KEEP with no BURST_AMPLIFIED_REPETITION unless repetition reasons also appear"
            ),
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
            f"{idx:02d}) sent eventId={event_id} ticker={case.ticker} author={case.author} -> "
            f"p={md.partition} off={md.offset}"
        )
        print(f"    expected: {case.expected}")
        time.sleep(0.15)

    producer.flush()
    producer.close()

    print("\nDone.")
    print(
        "Next: run the listener tester and filter by this runId to verify reasons/signals."
    )
    print(f"runId={run_id}")


if __name__ == "__main__":
    main()
