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

## Next Steps

1. Wire Kafka consumer → dummy scoring → MongoDB writes
2. Add MongoDB indexes + TTL
3. Validate backend API reads
4. Replace dummy scoring with real sentiment model
5. Improve aggregation and keyword extraction
