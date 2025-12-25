# Sentiment Service — Market-Like Sentiment Signal (Tier 2 + Signal Layer)

## Purpose

This service consumes **cleaned social events** from Kafka, performs **sentiment scoring + keyword extraction**, and produces a **market-like sentiment signal per ticker**.

Instead of exposing raw per-event or raw per-hour sentiment directly to the frontend, the service builds sentiment in **two layers**:

1. **Hourly per-ticker aggregates** (raw material, time series, TTL)
2. **A smoothed, market-style sentiment signal** (serving layer, one document per ticker)

This mirrors how financial indicators are constructed:

* noisy data → hourly “bars”
* bars → smoothed indicator (EMA)

The frontend never talks to Kafka and never scans large historical windows.
It consumes **pre-computed sentiment signals** via the backend API.

---

## Design Philosophy (Important)

> **Hourly sentiment is not the product.
> The sentiment signal is the product.**

Social sentiment is noisy:

* a single viral post can distort one hour
* low-volume hours are unreliable
* raw hourly values swing too much for users

To reflect **overall market sentiment**, this service:

* aggregates sentiment per hour
* smooths sentiment across hours
* weights hours with more data more heavily
* updates sentiment gradually when trends persist

This produces a signal that:

* behaves like a market indicator
* is stable but responsive
* scales well for many users

---

## Architecture Overview

### High-level data flow

1. **Ingestor Service** publishes RAW events
2. **Filtering Service A** standardizes and filters events → `CLEANED_EVENTS`
3. **Sentiment Service (this repo)**:

   * consumes `CLEANED_EVENTS`
   * scores sentiment + extracts keywords
   * incrementally builds **hourly aggregates**
   * periodically updates a **market-like sentiment signal**
4. **Backend API** reads MongoDB and serves frontend
5. **Frontend** polls backend APIs (cheap reads)

### Two processing tracks

#### 1️⃣ Streaming track (event-driven, always running)

* Kafka → per-event sentiment
* Updates **hourly aggregates** using atomic increments

#### 2️⃣ Signal track (time-driven, controlled)

* Periodically checks for completed hours
* Converts hourly aggregates into a **smoothed sentiment signal**
* Updates **one document per ticker**

---

## Storage Model (Tier 2 + Signal Layer)

### Why two layers?

| Layer             | Purpose                                |
| ----------------- | -------------------------------------- |
| Hourly aggregates | Truth, history, charts, debugging      |
| Signal layer      | Fast reads, stable UX, market behavior |

---

## MongoDB Atlas: What we write

### Database

* Example database name: `sentrix`

### Collections

### 1) `ticker_sentiment_hourly` — base time series (TTL)

Stores **one document per (ticker, hour)**.

This is the **raw material layer**, similar to market candles.

**Document meaning**

> “What did sentiment look like for this ticker during this hour?”

**Stored fields (conceptual)**:

* `_id`: `${ticker}|${hourStartUtc}`
* `ticker`
* `hourStartUtc`, `hourEndUtc`
* `count` (number of events)
* `scoreSum` (sum of sentiment scores)
* `keywordCounts` (frequency map)
* `sourceBreakdown`
* `updatedAtUtc`
* `expireAtUtc` (TTL)

**Retention**

* TTL index keeps only the last **7–30 days**
* Old data expires automatically

**Why this exists**

* historical charts
* transparency for demo
* backfills / recomputation
* debugging incorrect signals

---

### 2) `ticker_sentiment_signal` — market-like serving model

Stores **one document per ticker**.

This is what the **frontend primarily consumes**.

**Document meaning**

> “What is the current overall market sentiment for this ticker?”

**Stored fields (conceptual)**:

* `_id`: `ticker`
* `ticker`
* `signalScore` (EMA-smoothed sentiment)
* `halfLifeHours` or `alpha` (signal configuration)
* `lastAppliedHourStartUtc` (prevents double application)
* `updatedAtUtc`

**Optional (but useful)**

* `lastHourAvg`
* `lastHourCount`
* `recentVolume` (confidence indicator)
* `trend24h` / `trend1h`
* `keywords` (from most recent hour)

**Why this exists**

* O(1) reads per ticker
* no scanning 168 hours per request
* scalable to many users polling

---

## How the market-like signal is built

### Step 1 — Build hourly aggregates (continuous)

For each event:

1. Determine hour bucket (UTC)
2. Compute sentiment score
3. `$inc` into `ticker_sentiment_hourly`:

   * `count += 1`
   * `scoreSum += score`
   * `keywordCounts.* += 1`

This happens continuously.

---

### Step 2 — Apply hourly signal update (periodic)

On a fixed schedule (e.g. every minute):

1. Identify the **previous hour** (with a small grace window)
2. For each ticker:

   * read that hour’s `count` and `scoreSum`
   * compute `hourAvg = scoreSum / count`
3. Apply **exponentially weighted moving average (EMA)**:

   * recent hours matter more
   * sustained trends move the signal gradually
4. Update `ticker_sentiment_signal`
5. Record `lastAppliedHourStartUtc` to ensure **exactly-once behavior**

This produces market-style behavior:

* one bad hour ≠ crash
* many bad hours → signal drifts negative

---

## Frontend Consumption Model

### Main sentiment view (cheap)

Backend reads only:

* `ticker_sentiment_signal`

Used for:

* overview pages
* dashboards
* frequent polling

### Detailed views (on demand)

Backend reads:

* `ticker_sentiment_hourly`

Used for:

* charts
* explanations
* trend breakdowns

Frontend **never**:

* talks to Kafka
* scans raw events
* scans long history unnecessarily

---

## Why this scales well

* Writes are incremental and atomic
* Reads are constant-time per ticker
* Historical data is bounded by TTL
* Signal updates are controlled and replay-safe

---

## Operational Notes

* Service runs as a **long-running Kafka consumer**
* Hourly aggregation is continuous
* Signal update runs periodically
* MongoDB TTL enforces bounded storage
* Signal logic can evolve without changing upstream contracts


---
# Phases:
## 🟡 Phase 3 — Hourly Aggregation Logic (Streaming, Incremental)

### Goal

Build a **correct, replay-safe hourly time-series** from Kafka events.

At this stage, the hourly layer is treated as the **source of truth** for all downstream sentiment logic.

### What is built in this phase

* Consume cleaned Kafka events
* Convert event timestamps into **hour-aligned UTC buckets**
* Incrementally update MongoDB hourly documents:

  * `count`
  * `scoreSum`
  * `keywordCounts`
  * `sourceBreakdown`

This phase **does not** attempt to infer market sentiment yet.

### Files

* `utils/time.py`
* `domain/scoring.py` (stub)
* `storage/hourly_repo.py`
* `main.py` (partial wiring)

### Responsibilities

* Streaming-safe writes using `$inc`
* No read-before-write
* No cross-hour coupling
* No signal smoothing logic

### DoD

* Multiple Kafka events for the same `(ticker, hour)` produce a **single MongoDB document**
* Reprocessing events increases `count` and `scoreSum` deterministically
* TTL index correctly expires old hourly documents

> 💡 This phase intentionally ignores “market behavior”.
> It focuses only on building correct **hourly bars**.

---

## 🟡 Phase 4 — MongoDB Storage Layer (Hourly + Signal Schema)

### Goal

Establish **production-grade MongoDB persistence** for both:

1. Hourly time series
2. Signal serving model (schema only)

### What is built in this phase

* Mongo client lifecycle management
* Hourly repository with TTL
* Signal repository **schema and indexes only**

At this stage, the signal collection exists structurally but does **not yet implement EMA logic**.

### Files

* `storage/mongo_client.py`
* `storage/hourly_repo.py`
* `storage/signal_repo.py`

### Responsibilities

* Connection reuse
* Atomic upserts
* Correct indexing
* Clear separation of:

  * analytical store (hourly)
  * serving store (signal)

### DoD

* Hourly docs persist correctly with TTL
* Signal collection exists with one document per ticker
* No coupling between hourly writes and signal semantics yet

> 💡 Signal storage is introduced **early** so backend and frontend can be built against a stable contract.

---

## 🟡 Phase 5 — End-to-End Streaming Persistence (Kafka → Hourly)

### Goal

Complete the **real streaming path**:
Kafka → bucketing → scoring (stub) → hourly MongoDB writes.

This phase proves that the pipeline can run continuously and safely.

### What is built in this phase

* Kafka consumer loop
* Event validation and parsing
* Hour bucketing
* Stub sentiment scoring
* Incremental hourly MongoDB updates
* Offset commit only on success

### Files

* `main.py`
* `messaging/kafka_consumer.py`
* `storage/hourly_repo.py`

### Responsibilities

* Orchestration only
* No aggregation math inside Mongo
* No signal smoothing yet

### DoD

* Kafka ingestion runs continuously
* MongoDB hourly docs update correctly under load
* Restarting the service does not corrupt data

> 💡 This is the **first truly “working system” milestone**.

---

## 🟡 Phase 6 — Signal Placeholder (Hourly-Driven, Once per Hour)

### Goal

Introduce the **signal update lifecycle** without implementing EMA yet.

This phase exists to:

* unblock backend APIs
* unblock frontend polling
* lock in the signal update semantics

### What is built in this phase

* Time-based signal updater:

  * runs periodically
  * applies **exactly once per hour**
* Signal value computation is **placeholder logic**:

  * deterministic or random per `(ticker, hour)`
* Signal documents store:

  * `signalScore`
  * `asOfHourStartUtc`
  * `updatedAtUtc`

### Important constraints

* Signal is **not** updated per event
* Signal is **not** updated multiple times per hour
* Hour boundary is determined by:

  * clock time
  * grace window
  * `asOfHourStartUtc` guard

### Files

* `storage/signal_repo.py`
* `main.py` (signal updater hook)

### DoD

* Signal updates exactly once per hour per ticker
* Restarting the service does not reapply the same hour
* Backend can read signal documents cheaply

> 💡 This phase validates **signal mechanics**, not signal correctness.

---

## 🟢 Phase 7 — Idempotency, Stability & Ops Polish

### Goal

Harden the system for demos and grading.

### What is built

* Stability checks (grace window, `updatedAtUtc`)
* Clear logging around hour application
* Health/readiness endpoints
* Safer failure modes

### Files

* `observability/logging.py`
* `observability/health.py`

### DoD

* Clear operational visibility
* Failures are diagnosable
* Signal updater behaves predictably

---

## 🟢 Phase 8 — Real Market Signal (EMA / EWMA)

### Goal

Replace placeholder signal logic with **true market-style EMA**.

### What changes

* Signal computation logic only
* No schema changes
* No API changes
* No frontend changes

### Files

* `domain/signal.py` (or `domain/scoring.py` extension)

### DoD

* EMA applied once per hour
* Volume-weighted smoothing
* Stable, explainable sentiment behavior

---

## Updated Recommended Order

1. Phase 3 — Hourly aggregation (current)
2. Phase 4 — Mongo schema & repos (current)
3. Phase 5 — End-to-end Kafka → hourly (current focus)
4. Phase 6 — Signal placeholder (next)
5. Phase 7 — Ops polish
6. Phase 8 — EMA signal

---

### Key takeaway (for your report)

> The system is intentionally built **bottom-up**:
> hourly truth → signal mechanics → signal intelligence.

This framing will read **very well** to examiners.

If you want, next I can:

* help you write the **exact “Phase 6 signal updater” pseudo-flow** for the README, or
* sanity-check that Phase 5 code path matches the write-up line-by-line.
