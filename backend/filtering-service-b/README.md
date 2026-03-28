# Filtering Service B

Filtering Service B is the second-stage credibility filter in the Sentrix pipeline.
It consumes events from Filter A, applies semantic and behavioral checks, and publishes either KEEP or REJECT.

## What This Service Does

Input topic:
- `sentrix.filter-service-a.cleaned`

Output topics:
- `sentrix.filter-service-b.filtered`
- `sentrix.filter-service-b.rejected`

High-level flow:
1. Parse and validate cleaned event envelope.
2. Stage 1: score ticker relevance from embeddings.
3. Stage 2: score manipulation/repetition signals from Redis-backed short-term state.
4. Stage 3: score novelty/information value vs recent accepted same-ticker events.
5. Final threshold decision (`KEEP` or `REJECT`).
6. Publish result and update Redis state.
7. Emit per-event logs and rolling terminal summaries.

## Tech Stack

- Python 3.12
- Poetry
- FastAPI + Uvicorn
- Kafka (`confluent-kafka` for service runtime)
- Redis (short-term state)
- `sentence-transformers` (`all-MiniLM-L6-v2`)

Math/AI used:
- Cosine similarity on sentence embeddings (relevance + novelty)
- SimHash + Hamming distance (repetition/manipulation)
- Score accumulation with clamping and thresholding

## Project Layout

- `src/filtering_service_b/main.py` runtime bootstrap, Kafka consume/publish loop
- `src/filtering_service_b/pipeline/processor.py` core decision orchestration
- `src/filtering_service_b/relevance/*` Stage 1 modules
- `src/filtering_service_b/manipulation/*` Stage 2 modules
- `src/filtering_service_b/novelty/*` Stage 3 modules
- `src/filtering_service_b/state/*` Redis state stores
- `src/filtering_service_b/config/settings.py` env loading/validation
- `src/filtering_service_b/observability/*` logging + rolling metrics
- `tests/unit/*` unit tests

## Common Setup

From repo root:

```bash
cd backend/filtering-service-b
poetry lock
poetry install
```

If `poetry install` says lock is stale, run `poetry lock` first, then install again.

## Local Setup

Create local env file:

```bash
cd backend/filtering-service-b
cp .env.local.example .env.local
```

Recommended local env behavior:
- Kafka: `KAFKA_SECURITY_PROTOCOL=PLAINTEXT`
- Redis: leave `REDIS_URL` empty and use `REDIS_HOST=localhost`, `REDIS_PORT=6379`
- Keep `PORT=8012` unless you need a different local port

Optional speed-up for model fetch:
- Set `HF_TOKEN` in your shell or `.env.local` to reduce Hugging Face unauthenticated throttling warnings.

Run locally:

```bash
cd backend/filtering-service-b
set -a
source .env.local
set +a
poetry run python -m filtering_service_b.main
```

Run with explicit threshold override:

```bash
cd backend/filtering-service-b
set -a
source .env.local
set +a
FINAL_KEEP_THRESHOLD=0.40 poetry run python -m filtering_service_b.main
```

## Railway Setup

Create Railway env template copy:

```bash
cd backend/filtering-service-b
cp .env.railway.example .env.railway
```

In Railway variables, fill values from `.env.railway`:
- Kafka security for Confluent:
  - `KAFKA_SECURITY_PROTOCOL=SASL_SSL`
  - `KAFKA_SASL_MECHANISM=PLAIN`
  - `KAFKA_SASL_USERNAME=<API_KEY>`
  - `KAFKA_SASL_PASSWORD=<API_SECRET>`
- Redis:
  - preferred: set `REDIS_URL`
  - fallback: set `REDIS_HOST/PORT/DB/USERNAME/PASSWORD/SSL`

Suggested Railway service settings:
- Root Directory: `backend/filtering-service-b`
- Build Command: `poetry install --no-interaction --no-ansi`
- Start Command: `poetry run python -m filtering_service_b.main`

Notes:
- Runtime port is read from `PORT` env (Railway sets this automatically).
- Internal Redis hostnames like `redis.railway.internal` resolve only inside Railway.
- Prefer `poetry run ...` for consistent dependency/runtime behavior.

## How Filtering Works (Stage by Stage)

### Stage 1: Ticker Relevance

Goal:
- Check if text is actually about the ticker/company in finance context.

Method:
- Build event text (`title + normalized text` when title exists).
- Build ticker profile text from `tickers.json`.
- Embed both using `all-MiniLM-L6-v2`.
- Cosine similarity drives score delta bands.

Outcomes:
- Strong similarity (`>= RELEVANCE_STRONG_SIMILARITY_THRESHOLD`): optional small score boost.
- Medium similarity (`>= RELEVANCE_MEDIUM_SIMILARITY_THRESHOLD` and below strong): mild score penalty.
- Low similarity (`>= RELEVANCE_LOW_SIMILARITY_THRESHOLD` and below medium): stronger score penalty + `LOW_TICKER_RELEVANCE`.
- Extreme low similarity (`< RELEVANCE_LOW_SIMILARITY_THRESHOLD`): immediate reject path + `EXTREME_LOW_TICKER_RELEVANCE`.
- Unknown ticker profile: immediate reject path + `UNKNOWN_TICKER_PROFILE` (when `RELEVANCE_REJECT_UNKNOWN_TICKER_PROFILE=true`).

Why it exists:
- Prevent non-finance or off-ticker chatter from reaching sentiment model.
- Remove false positives from ambiguous ticker symbols (for example short symbols that can appear in unrelated text).
- Make later stages operate only on semantically plausible ticker content.

### Stage 2: Manipulation / Repetition

Goal:
- Detect coordinated copy-waves and repetitive ticker pushing.

Method:
- Compute SimHash from normalized text.
- Compare current event hash against recent same-ticker history from Redis (`tickerSimilarity` list).
- Compare current event hash against same-author same-ticker history from Redis (`authorTickerHistory` list).
- Use Hamming distance threshold (`MANIPULATION_*_MAX_HAMMING`) to decide near-duplicate matches.
- Count matches/unique authors/time-span to classify strength.
- Use burst context (`burstRatio`) only as a multiplier when repetition evidence already exists.

Main signals:
- Cross-user repetition (`CROSS_USER_REPETITION`)
- Dense similarity cluster (`DENSE_SIMILARITY_CLUSTER`)
- Same-account repetition (`SAME_ACCOUNT_REPETITION`)
- Burst-amplified repetition (`BURST_AMPLIFIED_REPETITION`)

Score behavior:
- Cross-user: apply base penalty after minimum match conditions; apply stronger penalty after strong-match threshold.
- Cluster density: additional penalty when many similar events from multiple authors appear in a short time span.
- Same-account: apply base/strong penalties by match count; optional hard reject for extreme repeats if enabled.
- Burst: no penalty by itself; only amplifies existing Stage 2 penalties.

Why it exists:
- Stage 1 alone can still allow coordinated but on-topic manipulation.
- Prevent campaigns from dominating sentiment with repeated text variants.
- Preserve organic repeated discussion while penalizing high-similarity waves.

### Stage 3: Novelty / Information Value

Goal:
- Downrank repetitive low-information chatter even if not obvious spam.

Method:
- Reuse embedding service.
- Compare current event text embedding with recent accepted same-ticker references from Redis (`acceptedNovelty` list).
- Use max similarity against the reference set as novelty proxy.
- Apply penalty bands for high similarity (redundant content).
- Optionally apply slight boost for clearly distinct content once enough references exist.

Main signal:
- `LOW_NOVELTY`

Score behavior:
- Similarity above medium novelty threshold: medium novelty penalty.
- Similarity above low novelty threshold: stronger novelty penalty.
- Similarity below distinct threshold (with enough references): small novelty boost.

Why it exists:
- Keeps downstream sentiment stream informative rather than redundant.
- Stops “same message, slightly reworded” chatter from flooding accepted stream.
- Still allows genuinely new updates on the same ticker.

### Final Decision

Score flow:
- Start from `1.0`.
- Add/subtract stage deltas.
- Clamp to `[0.0, 1.0]`.
- Apply overrides first (for hard reject paths), then threshold.

Default threshold:
- `FINAL_KEEP_THRESHOLD=0.40`

Decision:
- `score >= threshold` => `KEEP`
- otherwise => `REJECT`

## Single Event Walkthrough

Given one cleaned event from Filter A:
1. Service parses schema (`ingestorEvent`, `textView`, `filterMeta`).
2. Score starts at `1.0`.
3. Stage 1 compares event text embedding to ticker profile embedding:
- If strongly relevant, score may go slightly up.
- If medium/low relevance, score is reduced.
- If extreme irrelevant or unknown ticker profile, event is forced to reject path.
4. Service fetches Redis context for this ticker/author:
- same-ticker recent similarity history (`tickerSimilarity`)
- same-author same-ticker history (`authorTickerHistory`)
- accepted same-ticker novelty references (`acceptedNovelty`)
- burst counters (`burst`)
5. Stage 2 computes SimHash of current text, then compares against historical hashes:
- Cross-user near-duplicates reduce score.
- Dense cluster conditions reduce score more.
- Same-account near-duplicates reduce score (or force reject if extreme rule enabled).
- If burst ratio is high and repetition evidence exists, penalties are amplified.
6. Stage 3 computes novelty against accepted references:
- Very similar to recent accepted content => additional downvote (penalty).
- Clearly distinct from recent accepted content => small upvote (boost), if enough references exist.
7. Combined score is clamped to `[0, 1]`.
8. Final decision:
- Any hard-override reject condition wins first.
- Else threshold check decides KEEP/REJECT.
- Reject output score is normalized to `0.0` in envelope.
9. Envelope includes `decision`, `credibilityScore`, `decisionReasons`, and stage signals.
10. Event is published to filtered/rejected Kafka topic and state is written back to Redis for future comparisons.
11. Terminal logs print per-event line immediately; rolling summary prints every configured window.

## Testing

### Unit tests

```bash
cd backend/filtering-service-b
poetry run pytest -q tests/unit
```

### Integration-like Kafka event tests

From repo root:

```bash
python backend/event-testers/service-b-phase-3-test.py
python backend/event-testers/service-b-phase-4-test.py
python backend/event-testers/service-b-all-paths-test.py
```

Consume and inspect outputs for a run id:

```bash
python backend/event-testers/service-b-listener-tester.py --run-id <RUN_ID> --max-messages 60 --max-seconds 240
```

## Redis State Reset (Filter B Only)

Clear only Filter B keys (`fsb:v1:*`), not full Redis DB:

```bash
redis-cli -n 0 --scan --pattern 'fsb:v1:*' | while read k; do redis-cli -n 0 DEL "$k" >/dev/null; done
```

Verify cleared:

```bash
redis-cli -n 0 --scan --pattern 'fsb:v1:*' | wc -l
```

Expected count after clear: `0`

## Kafka Topic Commands

Create topics (example local Kafka CLI):

```bash
kafka-topics --bootstrap-server localhost:9092 --create --if-not-exists --topic sentrix.filter-service-a.cleaned --partitions 3 --replication-factor 1

kafka-topics --bootstrap-server localhost:9092 --create --if-not-exists --topic sentrix.filter-service-b.filtered --partitions 3 --replication-factor 1

kafka-topics --bootstrap-server localhost:9092 --create --if-not-exists --topic sentrix.filter-service-b.rejected --partitions 3 --replication-factor 1
```

List topics:

```bash
kafka-topics --bootstrap-server localhost:9092 --list
```

Inspect topic offsets quickly:

```bash
kafka-run-class kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic sentrix.filter-service-a.cleaned
```

## Terminal Observability

Per-event log includes:
- event id, ticker, decision, score, reasons, latency, topic/partition/offset

Rolling summary includes:
- keep/reject counts and reject rate
- invalid-input count
- avg/p95 latency
- avg score
- near-threshold percentage
- top reason counts

Tune via:
- `APP_ROLLING_SUMMARY_EVERY` (events per summary)
- `APP_NEAR_THRESHOLD_WINDOW` (score window around final threshold)
