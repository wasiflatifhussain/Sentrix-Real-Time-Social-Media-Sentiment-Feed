from __future__ import annotations

from pathlib import Path

import pandas as pd


CSV_PATH = Path("evaluation/data/ingestor_runs_2026-01-04_to_2026-01-10.csv")
WINDOW_START = pd.Timestamp("2026-01-04T00:00:00Z")
WINDOW_END = pd.Timestamp("2026-01-11T00:00:00Z")


def main() -> None:
    df = pd.read_csv(CSV_PATH)
    df["run_started_at_utc"] = pd.to_datetime(df["run_started_at_utc"], utc=True)

    window = df[(df["run_started_at_utc"] >= WINDOW_START) & (df["run_started_at_utc"] < WINDOW_END)]

    expected_hourly_runs = 7 * 24
    observed_runs = len(window)
    coverage_pct = (observed_runs / expected_hourly_runs) * 100 if expected_hourly_runs else 0.0

    attempts = (window["events_published_success"] + window["publish_failures"]).sum()
    successes = window["events_published_success"].sum()
    weighted_success_pct = (successes / attempts) * 100 if attempts else 0.0

    under_3m_pct = (window["run_latency_seconds"] < 180).mean() * 100 if observed_runs else 0.0
    in_4_to_5m_pct = (
        ((window["run_latency_seconds"] >= 240) & (window["run_latency_seconds"] <= 300)).mean() * 100
        if observed_runs
        else 0.0
    )
    above_5m_count = int((window["run_latency_seconds"] > 300).sum())

    print("Ingestor Assessment (2026-01-04 to 2026-01-10 UTC)")
    print("=" * 56)
    print(f"Runs observed: {observed_runs}")
    print(f"Hourly schedule coverage: {coverage_pct:.2f}% ({observed_runs}/{expected_hourly_runs})")
    print(f"Average per-run success rate: {window['run_success_rate_pct'].mean():.2f}%")
    print(f"Weighted overall success rate: {weighted_success_pct:.2f}%")
    print(f"Median latency: {window['run_latency_seconds'].median():.1f}s")
    print(f"P95 latency: {window['run_latency_seconds'].quantile(0.95):.1f}s")
    print(f"< 3 min latency runs: {under_3m_pct:.2f}%")
    print(f"4-5 min latency runs: {in_4_to_5m_pct:.2f}%")
    print(f"> 5 min latency runs: {above_5m_count}")


if __name__ == "__main__":
    main()
