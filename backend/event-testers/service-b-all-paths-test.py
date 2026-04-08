"""
seed_filter_b_all_paths_events.py

Publishes mixed Filter-A-cleaned envelopes directly into:
  sentrix.filter-service-a.cleaned

Use this single script to run a broad end-to-end verification set:
- Phase 3 relevance paths (happy/moderate/low/extreme/unknown/invalid)
- Phase 4 manipulation paths (cross-user, dense cluster, same-account, burst amplification)
- burst-only benign paths (high activity without repetition evidence)

Prereq:
  pip install kafka-python

Run:
  python backend/event-testers/service-b-all-paths-test.py
"""

from __future__ import annotations

import argparse
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
    invalid_payload: bool = False


def now_epoch() -> int:
    return int(time.time())


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed Filter B all-path test events")
    parser.add_argument("--bootstrap", default=BOOTSTRAP)
    parser.add_argument("--topic", default=FILTER_A_CLEANED_TOPIC)
    parser.add_argument("--reset-state", action="store_true")
    parser.add_argument("--redis-host", default="localhost")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--redis-db", type=int, default=0)
    return parser.parse_args()


def _mk_cleaned_envelope(run_id: str, index: int, case: SeedCase) -> dict:
    event_id = f"fball:{run_id}:{index:02d}:{case.case_id}"
    title = case.title.strip()
    body = case.body.strip()
    text_normalized = f"{title}\n{body}" if title else body

    return {
        "ingestorEvent": {
            # Keep authors run-scoped so old Redis state does not contaminate this run.
            "author": f"{case.author}:{run_id}",
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
    repeated_msft_text = (
        "MSFT cloud growth commentary is spreading quickly across posts. "
        "Watching Azure demand, enterprise bookings, and valuation response."
    )
    same_account_nvda_text = (
        "NVDA post repeating identical setup: data-center demand, earnings expectations, "
        "and the same short-term breakout levels."
    )
    aapl_benign = [
        (
            "AAPL product and services mix commentary with margin assumptions.",
            "KEEP, no repetition reasons expected",
        ),
        (
            "AAPL buyback cadence and free-cash-flow sustainability discussion.",
            "KEEP, no repetition reasons expected",
        ),
        (
            "AAPL valuation reset versus long-term earnings durability.",
            "KEEP, no repetition reasons expected",
        ),
        (
            "AAPL supply-chain and iPhone cycle discussion for next quarter.",
            "KEEP, burst may be high but no repetition reason expected",
        ),
    ]

    cases: list[SeedCase] = [
        # -------------------------
        # Phase 3 relevance checks
        # -------------------------
        SeedCase(
            case_id="p3_happy_strong",
            ticker="TSLA",
            author="allpaths-a",
            title="Tesla delivery growth and margin outlook",
            body=(
                "TSLA reported stronger deliveries and updated margin outlook. "
                "Discussion focuses on earnings quality and valuation for the stock."
            ),
            expected="KEEP with strong/moderate relevance",
        ),
        SeedCase(
            case_id="p3_happy_moderate",
            ticker="TSLA",
            author="allpaths-a2",
            title="TSLA watchlist setup",
            body=(
                "TSLA is on my watchlist into earnings because delivery and margin commentary "
                "can shift near-term valuation expectations."
            ),
            expected="KEEP (moderate/strong relevance)",
        ),
        SeedCase(
            case_id="p3_low_relevance",
            ticker="TSLA",
            author="allpaths-b",
            title="Daily routine update",
            body=(
                "Gym and coffee done. TSLA mentioned once in passing, but the post is mostly "
                "personal and not finance-focused."
            ),
            expected="KEEP with low relevance penalty or REJECT if very low similarity",
        ),
        SeedCase(
            case_id="p3_low_borderline",
            ticker="TSLA",
            author="allpaths-b2",
            title="Weekend notes",
            body=(
                "Mostly personal update about workouts and errands, with a quick TSLA mention "
                "but very little investing context."
            ),
            expected="KEEP with penalty OR REJECT (model-threshold dependent)",
        ),
        SeedCase(
            case_id="p3_extreme_irrelevant",
            ticker="TSLA",
            author="allpaths-c",
            title="Cooking prep notes",
            body="Meal prep and pasta recipe details only. No investing context.",
            expected="REJECT with EXTREME_LOW_TICKER_RELEVANCE",
        ),
        SeedCase(
            case_id="p3_unknown_ticker",
            ticker="ZZZZ",
            author="allpaths-d",
            title="Unknown ticker profile check",
            body="Discussing ZZZZ breakout and momentum.",
            expected="REJECT with UNKNOWN_TICKER_PROFILE",
        ),
        SeedCase(
            case_id="p3_invalid_payload",
            ticker="TSLA",
            author="allpaths-e",
            title="Malformed payload case",
            body="Missing textView intentionally.",
            expected="REJECT with INVALID_INPUT",
            invalid_payload=True,
        ),
        # -------------------------------
        # Phase 4 cross-user / cluster (MSFT, isolated from TSLA relevance cases)
        # -------------------------------
        SeedCase(
            case_id="p4_cross_seed_1",
            ticker="MSFT",
            author="allpaths-wave-a",
            title="MSFT flow watch",
            body=repeated_msft_text,
            expected="seed, usually no cross-user reason yet",
        ),
        SeedCase(
            case_id="p4_cross_seed_2",
            ticker="MSFT",
            author="allpaths-wave-b",
            title="MSFT flow watch",
            body=repeated_msft_text,
            expected="seed, usually no cross-user reason yet",
        ),
        SeedCase(
            case_id="p4_cross_trigger",
            ticker="MSFT",
            author="allpaths-wave-c",
            title="MSFT flow watch",
            body=repeated_msft_text,
            expected="CROSS_USER_REPETITION expected",
        ),
        SeedCase(
            case_id="p4_cluster_trigger",
            ticker="MSFT",
            author="allpaths-wave-d",
            title="MSFT flow watch",
            body=repeated_msft_text,
            expected="DENSE_SIMILARITY_CLUSTER likely (plus cross-user)",
        ),
        # --------------------------
        # Phase 4 same-account path (NVDA, isolated from TSLA/MSFT cases)
        # --------------------------
        SeedCase(
            case_id="p4_same_account_1",
            ticker="NVDA",
            author="allpaths-spammer",
            title="Repeated NVDA setup",
            body=same_account_nvda_text,
            expected="seed, usually no same-account reason yet",
        ),
        SeedCase(
            case_id="p4_same_account_2",
            ticker="NVDA",
            author="allpaths-spammer",
            title="Repeated NVDA setup",
            body=same_account_nvda_text,
            expected="seed or weak penalty depending history",
        ),
        SeedCase(
            case_id="p4_same_account_trigger",
            ticker="NVDA",
            author="allpaths-spammer",
            title="Repeated NVDA setup",
            body=same_account_nvda_text,
            expected="SAME_ACCOUNT_REPETITION expected, may REJECT if total score drops enough",
        ),
    ]

    # -----------------------------------------
    # Phase 4 burst-only benign activity checks
    # -----------------------------------------
    for idx, (body, expected) in enumerate(aapl_benign, start=1):
        cases.append(
            SeedCase(
                case_id=f"p4_burst_only_benign_{idx}",
                ticker="AAPL",
                author=f"allpaths-benign-{idx}",
                title=f"AAPL benign activity {idx}",
                body=body,
                expected=expected,
            )
        )

    # --------------------------------------------
    # Additional cross-user wave on second ticker (AMZN)
    # --------------------------------------------
    amzn_wave_text = (
        "AMZN retail+AWS demand commentary with nearly identical phrasing "
        "to simulate copy-wave behavior."
    )
    for idx, author in enumerate(("amzn-wave-a", "amzn-wave-b", "amzn-wave-c"), start=1):
        cases.append(
            SeedCase(
                case_id=f"p4_amzn_wave_{idx}",
                ticker="AMZN",
                author=author,
                title="AMZN copy-wave",
                body=amzn_wave_text,
                expected=(
                    "for later events: CROSS_USER_REPETITION expected; "
                    "cluster may appear on the 3rd+ event"
                ),
            )
        )

    return cases


def _reset_state(args: argparse.Namespace, cases: list[SeedCase]) -> None:
    try:
        import redis  # type: ignore[import-not-found]
    except Exception:
        print("WARN: redis package not available in this Python env; skipping --reset-state.")
        return

    client = redis.Redis(host=args.redis_host, port=args.redis_port, db=args.redis_db)

    tickers = sorted({case.ticker.upper() for case in cases})
    deleted = 0
    for ticker in tickers:
        exact_key = f"fsb:v1:ticker:{ticker}:similarity"
        deleted += int(client.delete(exact_key) or 0)

        for pattern in (
            f"fsb:v1:burst:ticker:{ticker}:*",
            f"fsb:v1:author:*:ticker:{ticker}:history",
        ):
            keys = client.keys(pattern)
            if keys:
                deleted += int(client.delete(*keys) or 0)

    print(
        f"State reset complete for tickers={tickers}; deleted_keys={deleted} "
        f"(redis={args.redis_host}:{args.redis_port}/{args.redis_db})"
    )


def main() -> None:
    args = _parse_args()
    run_id = uuid.uuid4().hex[:8]
    cases = build_cases()
    if args.reset_state:
        _reset_state(args, cases)

    producer = KafkaProducer(
        bootstrap_servers=args.bootstrap,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        linger_ms=5,
    )

    print(f"Run ID: {run_id}")
    print(f"Sending {len(cases)} cases -> {args.topic} @ {args.bootstrap}\n")
    print("Case guide:")
    print("- p3_*: relevance / invalid-input coverage")
    print("- p4_cross_* / p4_cluster_*: cross-user and dense cluster (MSFT)")
    print("- p4_same_account_*: same-account repetition progression (NVDA)")
    print("- p4_burst_only_benign_*: high activity without repetition evidence")
    print("- p4_amzn_wave_*: secondary copy-wave check on another ticker\n")

    for idx, case in enumerate(cases, start=1):
        payload = _mk_cleaned_envelope(run_id, idx, case)
        if case.invalid_payload:
            payload.pop("textView", None)
        event_id = payload["ingestorEvent"]["eventId"]
        headers = [
            ("decision", b"KEEP"),
            ("entityType", b"POST"),
            ("source", b"REDDIT"),
        ]
        md = producer.send(
            args.topic,
            key=event_id,
            value=payload,
            headers=headers,
        ).get(timeout=10)
        print(
            f"{idx:02d}) sent eventId={event_id} ticker={case.ticker} author={case.author}:{run_id} "
            f"-> p={md.partition} off={md.offset}"
        )
        print(f"    expected: {case.expected}")
        time.sleep(0.15)

    producer.flush()
    producer.close()
    print("\nDone.")
    print(
        "Next: run listener and filter by runId.\n"
        f"python backend/event-testers/service-b-listener-tester.py --run-id {run_id} --max-messages 60 --max-seconds 240"
    )


if __name__ == "__main__":
    main()
