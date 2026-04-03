from __future__ import annotations

from pathlib import Path

import pandas as pd


CSV_PATH = Path("evaluation/data/filter_a_runs_2026-01-04_to_2026-01-10.csv")
WINDOW_START = pd.Timestamp("2026-01-04T00:00:00Z")
WINDOW_END = pd.Timestamp("2026-01-11T00:00:00Z")


def main() -> None:
    df = pd.read_csv(CSV_PATH)
    df["run_started_at_utc"] = pd.to_datetime(df["run_started_at_utc"], utc=True)

    window = df[(df["run_started_at_utc"] >= WINDOW_START) & (df["run_started_at_utc"] < WINDOW_END)]

    expected_hourly_runs = 7 * 24
    observed_runs = len(window)
    coverage_pct = (observed_runs / expected_hourly_runs) * 100 if expected_hourly_runs else 0.0

    avg_removal_rate_pct = window["removal_rate_pct"].mean()
    weighted_removal_rate_pct = (
        window["total_dropped"].sum() / window["ingested_events"].sum() * 100
        if window["ingested_events"].sum() > 0
        else 0.0
    )

    min_removal_rate_pct = window["removal_rate_pct"].min()
    max_removal_rate_pct = window["removal_rate_pct"].max()

    throughput_mean = window["throughput_events_per_sec"].mean()
    throughput_p95 = window["throughput_events_per_sec"].quantile(0.95)

    total_dropped = int(window["total_dropped"].sum())
    dropped_invalid = int(window["dropped_invalid"].sum())
    dropped_duplicate = int(window["dropped_duplicate"].sum())
    dropped_spam = int(window["dropped_spam"].sum())

    manual_sample_total = int(window["manual_sample_size"].sum())
    manual_confirmed_invalid_total = int(window["manual_confirmed_invalid"].sum())
    manual_false_positive_total = int(window["manual_false_positive"].sum())
    manual_invalidity_confirm_rate_pct = (
        manual_confirmed_invalid_total / manual_sample_total * 100 if manual_sample_total > 0 else 0.0
    )

    print("Filtering Service-A Assessment (2026-01-04 to 2026-01-10 UTC)")
    print("=" * 72)
    print(f"Runs observed: {observed_runs}")
    print(f"Hourly schedule coverage: {coverage_pct:.2f}% ({observed_runs}/{expected_hourly_runs})")
    print(f"Average removal rate: {avg_removal_rate_pct:.2f}%")
    print(f"Weighted removal rate: {weighted_removal_rate_pct:.2f}%")
    print(f"Removal-rate range: {min_removal_rate_pct:.2f}% - {max_removal_rate_pct:.2f}%")
    print(f"Throughput mean: {throughput_mean:.2f} events/s")
    print(f"Throughput p95: {throughput_p95:.2f} events/s")
    print(
        "Dropped-event split: "
        f"invalid={dropped_invalid}, duplicate={dropped_duplicate}, spam={dropped_spam}, total={total_dropped}"
    )
    print(f"Manual verification sample size: {manual_sample_total}")
    print(f"Manual invalidity confirmation: {manual_invalidity_confirm_rate_pct:.2f}%")
    print(f"Manual false positives: {manual_false_positive_total}")


if __name__ == "__main__":
    main()
