# Evaluation Folder (Standalone)

This folder is fully standalone and does **not** require any microservice code changes.

It includes pre-filled ingestor run data for a 7-day window:

- Start date: `2026-01-04` (UTC)
- End date: `2026-01-10` (UTC)

## Files

- `data/ingestor_runs_2026-01-04_to_2026-01-10.csv`
- `data/ingestor_runs_2026-01-04_to_2026-01-10.json`
- `scripts/evaluate_ingestor.py`
- `notebooks/ingestor_assessment.ipynb`

## Run the Script

```bash
python3 evaluation/scripts/evaluate_ingestor.py
```

## Open the Notebook

```bash
jupyter notebook evaluation/notebooks/ingestor_assessment.ipynb
```

## What It Shows

- Per-run ingestion success percentage
- Weighted overall success percentage (across all publish attempts)
- Latency checks against your report thresholds:
  - target: `< 3 minutes` (180s)
  - upper acceptable bound: `4-5 minutes` (240-300s)
