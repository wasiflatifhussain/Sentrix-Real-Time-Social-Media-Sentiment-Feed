# Sentiment Service — Stream Scoring + Hourly Materialized Views (Tier 2)

## Purpose

This service consumes **cleaned social events** from Kafka, performs **sentiment scoring + keyword extraction**, and writes the results into **MongoDB Atlas** using a **Tier 2 storage strategy**:

- Store **hourly per-ticker aggregates** (materialized views) with a **TTL retention window**
- Also maintain a **latest snapshot per ticker** for fast reads
- **Do not store all per-event sentiment rows long-term** (avoids unnecessary volume)

The frontend remains “dumb”: it **polls the backend API**, which reads the aggregated results from MongoDB.

---

## Architecture Overview

### Data flow

1. **Ingestor Service** publishes RAW events (hourly batch)
2. **Filtering Service A** standardizes + drops obvious garbage and publishes to `CLEANED_EVENTS`

   - (Later: Filtering Service B can be inserted without changing this service, since event shape remains compatible)

3. **Sentiment Service (this repo)**:

   - consumes from Kafka `CLEANED_EVENTS`
   - computes sentiment + keywords (dummy logic for now)
   - updates **MongoDB Atlas** aggregates (Tier 2)

4. **Backend API** reads MongoDB and serves frontend
5. **Frontend** polls backend hourly (or more frequently, depending on UX)

### Key principle

- Kafka is the internal pipeline transport
- MongoDB Atlas holds **query-friendly materialized views**
- Frontend never talks to Kafka; it only calls backend APIs

---

## Tier 2 Storage Strategy (Recommended for FYP)

We store **per-ticker, per-hour** sentiment summaries (plus “latest per ticker”) instead of storing all event-level sentiment outputs.

### Why Tier 2?

- Efficient storage and fast queries for UI
- Enables charts / historical trend for a configurable window (e.g., last 7–30 days)
- Avoids large, redundant event-level sentiment storage
- Easy to debug and demo: “hourly bucket trend” reads cleanly

---

## Kafka: What this service reads (Input)

### Topic

- **Input topic:** `CLEANED_EVENTS`

  - Produced by Filtering Service A (and later Service B)
  - Keying recommendation: message key = `ticker` (helps ordering / partition locality)

### Expected event shape (high-level)

This service expects cleaned events to contain at least:

- `eventId` (unique id)
- `ticker` (single ticker per event, or one per emitted event if fan-out was done upstream)
- `source` (reddit/twitter/etc.)
- `entityType` (post/comment/etc.)
- `timestamp` (event creation time)
- `textNormalized` (cleaned text)

> Note: exact schema follows your existing “cleaned” event contract from Filtering Service A/B.
> The sentiment service treats it as the source of truth.

---

## Sentiment Analysis (Current vs Future)

### Current (MVP stub)

- The scoring step is implemented as **dummy logic / placeholder outputs**:

  - log `eventId` and `ticker`
  - emit fixed or random sentiment scores
  - emit sample keywords

This validates the **end-to-end pipeline** (Kafka → MongoDB → Backend → Frontend).

### Future (real scoring workflow)

The placeholder will be replaced with a real NLP pipeline, e.g.:

- Model: FinBERT / FinGPT / HuggingFace transformer
- Steps:

  1. tokenize normalized text
  2. infer sentiment logits / probabilities
  3. map to final score (e.g., -1..+1) and confidence
  4. extract keywords (TF-IDF / KeyBERT / attention-based heuristics)
  5. emit structured sentiment output for aggregation

**Important:** regardless of model choice, this service’s **storage contract remains unchanged**.

---

## MongoDB Atlas: What we write (Tier 2)

### Database

- Database name: `sentrix` (example)

### Collections

1. `ticker_sentiment_hourly` — hourly materialized view
2. `ticker_sentiment_latest` — latest snapshot per ticker

---

### 1) `ticker_sentiment_hourly`

One document per `(ticker, hourStart)`.

**Document shape (proposed):**

- `_id`: `${ticker}|${hourStartISO}`
- `ticker`: string
- `hourStart`: ISO timestamp (UTC, aligned to hour)
- `hourEnd`: ISO timestamp
- `score`: number
- `keywords`: string[]
- `count`: number
- `sourceBreakdown`: map (optional)
- `updatedAt`: ISO timestamp

**Retention (TTL):**

- TTL index on `hourEnd` (or `hourStart`)
- Example retention: **30 days**

---

### 2) `ticker_sentiment_latest`

One document per ticker.

**Document shape (proposed):**

- `_id`: `ticker`
- `ticker`: string
- `score`: number
- `keywords`: string[]
- `hourStart`: ISO timestamp
- `hourEnd`: ISO timestamp
- `count`: number
- `updatedAt`: ISO timestamp

This collection is optimized for fast backend reads.

---

## How aggregation is updated (high-level)

For each consumed cleaned event:

1. Determine the **hour bucket**
2. Produce per-event sentiment (stub now, real model later)
3. Update `ticker_sentiment_hourly`:

   - increment count
   - update score (e.g., weighted average)
   - update bounded keyword list

4. Update `ticker_sentiment_latest`

Aggregation logic is **decoupled from storage** and can evolve independently.

---

## Frontend delivery: Polling via Backend API

### Frontend does NOT poll MongoDB or Kafka.

Frontend polls the **backend API**:

- `GET /api/users/me/subscribed-tickers/sentiment`
- Backend resolves subscriptions and queries `ticker_sentiment_latest`

### Polling cadence

- Upstream updates hourly
- Frontend polls every **5–10 minutes** or on page focus/refresh

### Optional (later)

- Backend may push updates via SSE/WebSockets using MongoDB Change Streams
- Sentiment service remains unchanged

---

## Dependency Management (Poetry)

This project uses **Poetry** for dependency management and environment isolation.

- Dependencies are declared in `pyproject.toml`
- Exact versions are locked in `poetry.lock`
- Virtual environments are **managed automatically by Poetry**
- Developers do **not manually create or activate venvs**

### Common commands

```
poetry install
poetry add <dependency>
poetry add --group dev <dev-dependency>
poetry run python src/sentiment_service/main.py
poetry run pytest
```

This is conceptually equivalent to Maven/Gradle in Java projects.

---

## Tech Stack (Proposed)

### Sentiment Service

- Python **3.11+**
- Poetry (dependency & environment management)
- Kafka consumer (`confluent-kafka`)
- MongoDB Atlas (`pymongo`)
- Environment-based configuration (`.env`)
- Structured logging
- Optional health/readiness endpoints

### Backend API (separate service)

- Java Spring Boot or Node.js
- Reads MongoDB Atlas
- Serves REST APIs

### Frontend

- Polls backend REST endpoints
- Renders latest sentiment per subscribed ticker
- Optional charts from hourly buckets

---

## Proposed Folder Structure (Detailed, Production-Friendly)

```
sentiment-service/
├─ README.md
├─ pyproject.toml
├─ poetry.lock
├─ .env.example
├─ src/
│  └─ sentiment_service/
│     ├─ __init__.py
│     ├─ main.py                 # service entrypoint (Kafka consumer loop)
│     ├─ config/
│     │  ├─ __init__.py
│     │  └─ settings.py          # env-based config (Kafka, Mongo, retention)
│     ├─ messaging/
│     │  ├─ __init__.py
│     │  ├─ kafka_consumer.py    # Kafka consumption + offset handling
│     │  └─ schemas.py           # cleaned event adapters / validation
│     ├─ domain/
│     │  ├─ __init__.py
│     │  ├─ models.py            # CleanedEvent, SentimentResult, HourBucket
│     │  ├─ scoring.py           # sentiment scoring interface (stub → model)
│     │  ├─ keywords.py          # keyword extraction logic
│     │  └─ aggregation.py       # hourly aggregation logic (avg/weighted avg)
│     ├─ storage/
│     │  ├─ __init__.py
│     │  ├─ mongo_client.py      # MongoDB connection handling
│     │  ├─ hourly_repo.py       # writes to ticker_sentiment_hourly
│     │  └─ latest_repo.py       # writes to ticker_sentiment_latest
│     ├─ observability/
│     │  ├─ __init__.py
│     │  ├─ logging.py           # structured logging setup
│     │  └─ health.py            # optional liveness/readiness checks
│     └─ utils/
│        ├─ __init__.py
│        └─ time.py              # hour bucketing & timezone helpers
├─ tests/
│  ├─ test_aggregation.py
│  ├─ test_bucketing.py
│  └─ test_storage_contracts.py
└─ scripts/
   ├─ seed_cleaned_events.py     # publish test events to CLEANED_EVENTS
   └─ backfill_hourly.py         # optional replay / recomputation utilities
```

---

## Operational Notes

- Runs as a **long-running Kafka consumer**
- Naturally processes data hourly if upstream publishes hourly
- MongoDB TTL ensures bounded storage growth
- Aggregation logic can be enhanced without breaking APIs

---

## ✅ Phase 0 — DONE (Kafka Ingestion)

**Status:** ✔ Completed
You already did this correctly.

### Goal

* Consume events reliably
* Parse envelope
* Manual commit only on success

### Files

* `main.py`
* `kafka_consumer.py`
* `schemas.py`
* `settings.py`

### DoD

* Logs show eventId / ticker / partition / offset
* Restart resumes from last offset
* Bad messages do not get committed

✅ **You’re here**

---

## 🟡 Phase 1 — Time Bucketing (Pure Function Layer)

### Goal

Convert event timestamps → **hour-aligned UTC buckets**

This is foundational. Everything else depends on it.

### What to build

* A **pure helper** that:

  * takes epoch seconds
  * returns `(hourStart, hourEnd)` in UTC
* No Kafka
* No Mongo
* No side effects

### Files

* `utils/time.py`

### Responsibilities

* Normalize timestamps
* Align to hour boundary
* Handle missing timestamps safely

### DoD

* Unit tests for:

  * normal timestamps
  * boundary cases (e.g. 12:59 → 12:00)
  * UTC correctness

> 💡 This is intentionally boring — boring = correct.

---

## 🟡 Phase 2 — Sentiment Scoring Stub (Domain Layer)

### Goal

Introduce a **stable scoring interface** without real ML yet

### What to build

* A function/class that:

  * accepts `CleanedEvent`
  * returns `SentimentResult`
* Output is deterministic or random (doesn’t matter)

### Files

* `domain/models.py`
* `domain/scoring.py`

### Responsibilities

* Define the **contract** for scoring
* Decouple scoring from Kafka & Mongo

### DoD

* Given a CleanedEvent → returns:

  * score (float)
  * keywords (list[str])
  * confidence (optional)
* No external dependencies
* Easily replaceable later

> 💡 This is where ML will plug in later — don’t rush it now.

---

## 🟡 Phase 3 — Aggregation Logic (Pure + Stateful)

### Goal

Aggregate **per-event scores** into **hourly summaries**

### What to build

* Logic that updates:

  * count
  * average score (or weighted avg)
  * bounded keyword list

### Files

* `domain/aggregation.py`

### Responsibilities

* Pure math
* No Mongo
* No Kafka

### DoD

* Given:

  * existing aggregate
  * new sentiment result
* Returns:

  * updated aggregate

> 💡 This must be **idempotent-friendly** (replays should not corrupt state).

---

## 🟡 Phase 4 — MongoDB Integration (Storage Layer)

### Goal

Persist aggregates into MongoDB **safely**

### What to build

* Mongo client setup
* Repositories for:

  * hourly view
  * latest snapshot

### Files

* `storage/mongo_client.py`
* `storage/hourly_repo.py`
* `storage/latest_repo.py`

### Responsibilities

* Connection management
* Atomic updates (`$inc`, `$set`, `$setOnInsert`)
* TTL compatibility

### DoD

* Can upsert hourly document
* Can upsert latest document
* Safe under replay
* TTL index documented (can be manual)

> 💡 Mongo is your *state store* — treat it carefully.

---

## 🟡 Phase 5 — Wire Everything Together (End-to-End)

### Goal

Kafka → Scoring → Bucketing → Aggregation → Mongo

### What to build

* Glue code inside `main.py`

### Files

* `main.py` (updated)
* Everything else reused

### Responsibilities

* Orchestration only
* No business logic here

### DoD

* Consume one Kafka event
* Mongo shows:

  * updated hourly doc
  * updated latest doc
* Restart service → no duplication

---

## 🟡 Phase 6 — Idempotency & Replay Safety

### Goal

Make replays **safe and expected**

### What to build

* Ensure:

  * no double-counting
  * deterministic aggregation
* Possibly use:

  * eventId sets
  * monotonic hour updates
  * careful `$inc` logic

### Files

* `domain/aggregation.py`
* `storage/*`

### DoD

* Replaying same Kafka data does not corrupt aggregates
* Safe for demo and grading

---

## 🟢 Phase 7 — Observability & Ops Polish (Optional but Impressive)

### Goal

Make the service **demo- and prod-friendly**

### What to build

* Health endpoint
* Better logs
* Basic metrics

### Files

* `observability/health.py`
* `observability/logging.py`

### DoD

* Health check works
* Logs are readable
* Failures are diagnosable

---

## 🟢 Phase 8 — Real Sentiment Model (Post-Core)

### Goal

Replace stub scoring with real NLP

### What to build

* FinBERT / HF pipeline
* Batch or per-event inference

### Files

* `domain/scoring.py`

### DoD

* Same interface
* Better results
* No storage changes needed

---

# Recommended Order (Very Important)

**Do NOT skip around. Follow this order exactly:**

1. Phase 1 — Time bucketing
2. Phase 2 — Scoring stub
3. Phase 3 — Aggregation math
4. Phase 4 — Mongo writes
5. Phase 5 — Full wiring
6. Phase 6 — Replay safety

This minimizes bugs and rework.

---

## Where you are now

✅ Kafka ingestion
⏭ **Next: Phase 1 — Time Bucketing**

If you want, next I can:

* design `HourBucket` exactly
* give you the time bucketing helper + tests
* or sketch the Mongo update patterns **before** you code them

Just tell me which phase you want to start next.

