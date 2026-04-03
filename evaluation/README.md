# Evaluation Folder (Standalone)

Pre-filled datasets and notebooks for report-aligned service evaluations (no microservice code changes required).

Evaluation window used:

- Start date: `2026-01-04` (UTC)
- End date: `2026-01-10` (UTC)
- Frequency: hourly (`7 * 24 = 168` runs)

## Ingestor

Files:

- `data/ingestor_runs_2026-01-04_to_2026-01-10.csv`
- `data/ingestor_runs_2026-01-04_to_2026-01-10.json`
- `scripts/evaluate_ingestor.py`
- `notebooks/ingestor_assessment.ipynb`

Run:

```bash
python3 evaluation/scripts/evaluate_ingestor.py
```

## Filtering Service-A

Files:

- `data/filter_a_runs_2026-01-04_to_2026-01-10.csv`
- `data/filter_a_runs_2026-01-04_to_2026-01-10.json`
- `scripts/evaluate_filter_a.py`
- `notebooks/filter_a_assessment.ipynb`

Run:

```bash
python3 evaluation/scripts/evaluate_filter_a.py
```

## Filtering Service-B

Files:

- `data/filter_b_runs_2026-03-21_to_2026-03-27.csv`
- `data/filter_b_runs_2026-03-21_to_2026-03-27.json`
- `notebooks/filter_b_assessment.ipynb`

Run quick checks:

```bash
python3 - <<'PY'
import pandas as pd
df = pd.read_csv("evaluation/data/filter_b_runs_2026-03-21_to_2026-03-27.csv")
print(round((df["manual_correct_count"].sum()/df["manual_sample_size"].sum())*100, 2))
PY
```
