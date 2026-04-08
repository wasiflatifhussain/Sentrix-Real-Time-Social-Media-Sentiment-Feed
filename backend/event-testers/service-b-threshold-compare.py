"""
compare_filter_b_threshold_runs.py

Compares Filter B outputs across multiple threshold runs.

Expected workflow:
1) Run the same publisher scenario multiple times, each with different FINAL_KEEP_THRESHOLD.
2) Pass labeled run IDs to this script.
3) Get side-by-side decisions/scores per case.

Example:
  python backend/event-testers/service-b-threshold-compare.py \
    --run 0.30:runid_a \
    --run 0.40:runid_b \
    --run 0.50:runid_c
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass

from kafka import KafkaConsumer

BOOTSTRAP = "localhost:9092"
FILTERED_TOPIC = "sentrix.filter-service-b.filtered"
REJECTED_TOPIC = "sentrix.filter-service-b.rejected"


@dataclass(frozen=True)
class RunSpec:
    label: str
    run_id: str


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare Filter B outputs by run-id.")
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        help="Run spec in form LABEL:RUN_ID (repeatable). Example: 0.40:abc123de",
    )
    parser.add_argument("--bootstrap", default=BOOTSTRAP)
    parser.add_argument("--group-id", default=f"filter-b-threshold-compare-{int(time.time())}")
    parser.add_argument("--max-seconds", type=int, default=180)
    parser.add_argument("--poll-ms", type=int, default=1000)
    parser.add_argument("--print-missing", action="store_true")
    return parser.parse_args()


def _parse_run_specs(raw_specs: list[str]) -> list[RunSpec]:
    specs: list[RunSpec] = []
    for raw in raw_specs:
        if ":" not in raw:
            raise ValueError(f"Invalid --run '{raw}'. Expected LABEL:RUN_ID")
        label, run_id = raw.split(":", 1)
        label = label.strip()
        run_id = run_id.strip()
        if not label or not run_id:
            raise ValueError(f"Invalid --run '{raw}'. Empty label or run_id")
        specs.append(RunSpec(label=label, run_id=run_id))
    return specs


def _extract_case_id(event_id: str) -> str:
    # Expected eventId pattern from seeder:
    # fball:<runid>:<idx>:<case_id>
    parts = event_id.split(":", 3)
    if len(parts) == 4:
        return parts[3]
    return event_id


def _collect_outputs(
    specs: list[RunSpec],
    bootstrap: str,
    group_id: str,
    max_seconds: int,
    poll_ms: int,
) -> dict[str, dict[str, dict[str, object]]]:
    by_label: dict[str, dict[str, dict[str, object]]] = {s.label: {} for s in specs}
    run_id_to_label = {s.run_id: s.label for s in specs}

    consumer = KafkaConsumer(
        FILTERED_TOPIC,
        REJECTED_TOPIC,
        bootstrap_servers=bootstrap,
        group_id=group_id,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=lambda b: json.loads(b.decode("utf-8")),
        key_deserializer=lambda b: b.decode("utf-8") if b else None,
        consumer_timeout_ms=poll_ms,
    )

    start = time.time()
    try:
        while time.time() - start <= max_seconds:
            progressed = False
            for msg in consumer:
                progressed = True
                payload = msg.value if isinstance(msg.value, dict) else {}
                ing = payload.get("ingestorEvent") or {}
                meta = payload.get("filterMeta") or {}
                signals = meta.get("signals") or {}

                event_id = str(ing.get("eventId", ""))
                if not event_id:
                    continue

                matched_label = None
                for run_id, label in run_id_to_label.items():
                    if run_id in event_id:
                        matched_label = label
                        break
                if matched_label is None:
                    continue

                case_id = _extract_case_id(event_id)
                by_label[matched_label][case_id] = {
                    "eventId": event_id,
                    "decision": meta.get("decision"),
                    "score": meta.get("credibilityScore"),
                    "reason": meta.get("filterReason"),
                    "reasons": meta.get("decisionReasons"),
                    "crossUser": signals.get("stage2CrossUserTriggered"),
                    "cluster": signals.get("stage2ClusterTriggered"),
                    "sameAccount": signals.get("stage2SameAccountTriggered"),
                    "burstAmplified": signals.get("stage2BurstAmplified"),
                    "noveltyBand": signals.get("stage3NoveltyBand"),
                    "finalMode": signals.get("finalDecisionMode"),
                }
            if not progressed:
                time.sleep(0.2)
    finally:
        consumer.close()

    return by_label


def _print_report(
    specs: list[RunSpec],
    by_label: dict[str, dict[str, dict[str, object]]],
    print_missing: bool,
) -> None:
    labels = [s.label for s in specs]
    all_case_ids: set[str] = set()
    for label in labels:
        all_case_ids.update(by_label[label].keys())

    print("\n=== Threshold Comparison ===")
    print("labels:", ", ".join(labels))
    print(f"total_cases_seen={len(all_case_ids)}")

    for case_id in sorted(all_case_ids):
        row_parts = [f"\ncase={case_id}"]
        missing_any = False
        for label in labels:
            rec = by_label[label].get(case_id)
            if rec is None:
                missing_any = True
                row_parts.append(f"  [{label}] MISSING")
                continue
            row_parts.append(
                f"  [{label}] decision={rec['decision']} score={rec['score']} "
                f"reason={rec['reason']} reasons={rec['reasons']} "
                f"cross={rec['crossUser']} cluster={rec['cluster']} same={rec['sameAccount']} "
                f"burst={rec['burstAmplified']} novelty={rec['noveltyBand']} mode={rec['finalMode']}"
            )
        if missing_any and not print_missing:
            continue
        print("\n".join(row_parts))

    print("\n=== Summary (decision counts) ===")
    for label in labels:
        keep = 0
        reject = 0
        for rec in by_label[label].values():
            if rec.get("decision") == "KEEP":
                keep += 1
            elif rec.get("decision") == "REJECT":
                reject += 1
        print(f"{label}: KEEP={keep} REJECT={reject} TOTAL={keep + reject}")


def main() -> None:
    args = _parse_args()
    specs = _parse_run_specs(args.run)
    by_label = _collect_outputs(
        specs=specs,
        bootstrap=args.bootstrap,
        group_id=args.group_id,
        max_seconds=args.max_seconds,
        poll_ms=args.poll_ms,
    )
    _print_report(specs=specs, by_label=by_label, print_missing=args.print_missing)


if __name__ == "__main__":
    main()
