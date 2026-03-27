"""
listen_filter_b_outputs.py

Consumes Filtering Service B output topics and prints compact verification lines.

Topics:
- sentrix.filter-service-b.filtered
- sentrix.filter-service-b.rejected

Usage examples:
  python backend/event-testers/service-b-listener-tester.py --run-id ab12cd34 --max-messages 5
  python backend/event-testers/service-b-listener-tester.py --max-seconds 120

Prereq:
  pip install kafka-python
"""

from __future__ import annotations

import argparse
import json
import time

from kafka import KafkaConsumer

BOOTSTRAP = "localhost:9092"
FILTERED_TOPIC = "sentrix.filter-service-b.filtered"
REJECTED_TOPIC = "sentrix.filter-service-b.rejected"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Listen to Filter B outputs")
    parser.add_argument("--bootstrap", default=BOOTSTRAP)
    parser.add_argument("--run-id", default=None, help="Only show events with eventId containing this run id")
    parser.add_argument("--group-id", default=f"filter-b-listener-{int(time.time())}")
    parser.add_argument("--max-messages", type=int, default=50)
    parser.add_argument("--max-seconds", type=int, default=180)
    return parser.parse_args()


def _extract_summary(topic: str, payload: dict) -> str:
    ing = payload.get("ingestorEvent") or {}
    meta = payload.get("filterMeta") or {}
    signals = meta.get("signals") or {}

    event_id = ing.get("eventId", "<missing-eventId>")
    ticker = ing.get("ticker", "<missing-ticker>")
    decision = meta.get("decision", "<missing-decision>")
    reason = meta.get("filterReason")
    reasons = meta.get("decisionReasons")
    score = meta.get("credibilityScore")

    stage = signals.get("stage")
    band = signals.get("relevanceBand")
    sim = signals.get("relevanceSimilarity")
    cross_user = signals.get("stage2CrossUserTriggered")
    cluster = signals.get("stage2ClusterTriggered")
    same_account = signals.get("stage2SameAccountTriggered")
    burst = signals.get("stage2BurstAmplified")
    burst_ratio = signals.get("stage2BurstRatio")
    burst_extra = signals.get("stage2BurstExtraPenaltyApplied")

    return (
        f"topic={topic} eventId={event_id} ticker={ticker} decision={decision} "
        f"reason={reason} reasons={reasons} score={score} stage={stage} "
        f"band={band} similarity={sim} "
        f"crossUser={cross_user} cluster={cluster} sameAccount={same_account} "
        f"burstAmplified={burst} burstRatio={burst_ratio} burstExtra={burst_extra}"
    )


def main() -> None:
    args = _parse_args()

    consumer = KafkaConsumer(
        FILTERED_TOPIC,
        REJECTED_TOPIC,
        bootstrap_servers=args.bootstrap,
        group_id=args.group_id,
        auto_offset_reset="latest",
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
    )

    print(f"Listening on [{FILTERED_TOPIC}, {REJECTED_TOPIC}] @ {args.bootstrap}")
    if args.run_id:
        print(f"Filter: eventId contains run-id '{args.run_id}'")

    seen = 0
    start = time.time()

    try:
        for msg in consumer:
            payload = msg.value if isinstance(msg.value, dict) else {}
            ing = payload.get("ingestorEvent") or {}
            event_id = str(ing.get("eventId", ""))

            if args.run_id and args.run_id not in event_id:
                continue

            print(_extract_summary(msg.topic, payload))
            seen += 1

            if seen >= args.max_messages:
                print("Reached max-messages limit.")
                break

            if time.time() - start >= args.max_seconds:
                print("Reached max-seconds limit.")
                break
    finally:
        consumer.close()

    print(f"Done. matched_messages={seen}")


if __name__ == "__main__":
    main()
