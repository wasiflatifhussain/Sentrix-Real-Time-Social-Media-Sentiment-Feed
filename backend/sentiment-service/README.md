# Sentiment Service — Market-Like Sentiment Signal (Hourly + Serving API)

## Purpose

This service consumes **cleaned social events** from Kafka, performs **sentiment scoring and keyword extraction**, and exposes sentiment data through a **backend API** for frontend consumption.

The system intentionally separates sentiment processing into **two layers**:

1. **Hourly per-ticker aggregates** (raw, time-series data)
2. **Latest sentiment signal per ticker** (fast, serving-layer snapshot)

This mirrors how market data systems work:

> noisy events → hourly bars → indicator snapshot

The frontend never consumes Kafka data directly and never scans large event histories.
It polls **pre-computed MongoDB data** through a stable API.

---

## What is implemented now (scope of current system)

### ✔ Implemented

* Kafka → hourly sentiment aggregation (streaming, incremental)
* MongoDB storage with TTL for hourly data
* Periodic signal updater (placeholder logic)
* One latest signal document per ticker
* FastAPI backend exposing:

  * list of tickers
  * latest signals (single or many)
  * hourly sentiment history for charts

### ❌ Not implemented yet (by design)

* Historical signal (EMA) time-series storage
* Real sentiment model (currently stubbed)
* Advanced indicators (trend, confidence, decay curves)

These are listed under **Future Improvements**.

---

## High-Level Architecture

### Data flow

1. **Ingestor Service**

   * Publishes raw social events to Kafka

2. **Filtering Service**

   * Normalizes, filters, deduplicates
   * Publishes cleaned events

3. **Sentiment Service (this repo)**

   * Consumes cleaned events
   * Scores sentiment (stub)
   * Builds hourly aggregates
   * Periodically updates latest signal

4. **Backend API (FastAPI)**

   * Reads MongoDB only
   * Serves frontend requests

5. **Frontend**

   * Polls backend APIs
   * Displays dashboard + charts

---

## Processing Model

### 1) Streaming path (event-driven)

Runs continuously.

For each cleaned Kafka event:

* Bucket event into UTC hour
* Compute sentiment score (stub)
* Increment hourly MongoDB document using `$inc`

Result:

* Exactly one MongoDB document per `(ticker, hour)`
* Replay-safe, no read-before-write

---

### 2) Signal update path (time-driven)

Runs periodically (e.g. every minute).

Logic:

* Determine the most recent **fully closed hour** (with grace window)
* For each active ticker:

  * Read that hour’s aggregate
  * Compute a placeholder signal value
  * Update **one signal document per ticker**
  * Guard against double application using `asOfHourStartUtc`

Result:

* Latest signal snapshot per ticker
* Cheap reads for frontend
* No historical signal stored yet

---

## Storage Model (MongoDB)

### Database

Example: `sentrix`

---

### Collection: `ticker_sentiment_hourly`

**Purpose:**
Raw time-series data for charts, debugging, and recomputation.

**One document per (ticker, hour)**

**Key fields:**

* `_id`: `${ticker}|${hourStartUtc}`
* `ticker`
* `hourStartUtc`, `hourEndUtc`
* `count`
* `scoreSum`
* `keywordCounts`
* `sourceBreakdown`
* `updatedAtUtc`
* `expireAtUtc` (TTL)

**Retention:**

* Automatically expires after configured TTL (e.g. 7–30 days)

**Used for:**

* Hourly sentiment charts
* Transparency and demo
* Future signal recomputation

---

### Collection: `ticker_sentiment_signal`

**Purpose:**
Serving-layer snapshot of **current sentiment per ticker**.

**One document per ticker**

**Key fields:**

* `_id`: `ticker`
* `ticker`
* `signalScore`
* `asOfHourStartUtc`
* `updatedAtUtc`

**Optional fields (future):**

* `recentVolume`
* `keywords`
* `halfLifeHours`
* trend indicators

**Used for:**

* Dashboards
* Fast polling
* Overview pages

---

## Backend API

All endpoints are prefixed with:

```
/api/v1
```

---

### `GET /api/v1/health`

**Purpose:**
Health check endpoint.

**Returns:**

```json
{ "ok": true }
```

Used for monitoring and sanity checks.

---

### `GET /api/v1/tickers`

**Purpose:**
List all tickers currently present in the system.

Used to populate frontend dropdowns / autocomplete.

**Query params:**

* `limit` (optional, default 2000)

**Returns:**

```json
{
  "tickers": ["AAPL", "TSLA", "MSFT"],
  "count": 3
}
```

---

### `POST /api/v1/signals/latest`

**Purpose:**
Fetch latest sentiment signals for **multiple tickers at once**.

Used by dashboard list views.

**Request body:**

```json
{
  "tickers": ["AAPL", "TSLA", "MSFT"]
}
```

**Returns:**

```json
{
  "requested": ["AAPL", "TSLA", "MSFT"],
  "found": 3,
  "signals": {
    "AAPL": { ... },
    "TSLA": { ... }
  }
}
```

---

### `GET /api/v1/tickers/{ticker}/sentiment`

**Purpose:**
Fetch detailed sentiment data for **one ticker**.

Used for:

* detail pages
* charts

**Query params:**

* `hours` (default 48, max 336)

**Returns:**

```json
{
  "ticker": "TSLA",
  "signal": { ... },
  "hourly": [
    { "hourStartUtc": ..., "count": ..., "scoreSum": ... }
  ]
}
```

---

## How charts work (current behavior)

* Charts use **hourly aggregates**
* Data reflects **raw hourly sentiment**, not smoothed signal
* This is intentional and correct for a first version

Dashboard:

* shows **latest signal**

Charts:

* show **what happened per hour**

---

## How to run the system locally

### Terminal 1 — Sentiment Service (Kafka consumer + signal updater)

```bash
poetry install
poetry run python -m sentiment_service.main
```

This starts:

* Kafka consumer
* hourly aggregation
* signal updater loop

---

### Terminal 2 — Backend API (FastAPI)

Install API dependencies if not already installed:

```bash
poetry add fastapi uvicorn
```

Run API server:

```bash
poetry run uvicorn sentiment_service.api.app:app --host 0.0.0.0 --port 8000
```

API base URL (local):

```
http://localhost:8000/api/v1
```

---

## Testing with Postman

### Health

```
GET http://localhost:8000/api/v1/health
```

---

### List tickers

```
GET http://localhost:8000/api/v1/tickers
```

---

### Latest signals (multiple tickers)

```
POST http://localhost:8000/api/v1/signals/latest
```

Body:

```json
{
  "tickers": ["TSLA", "AAPL"]
}
```

---

### Ticker detail + chart data

```
GET http://localhost:8000/api/v1/tickers/TSLA/sentiment?hours=48
```

---

## Future Improvements

### 1) Real sentiment model

* Replace stub sentiment scorer with:

  * transformer model
  * lexicon-based scoring
  * or hybrid approach

### 2) Historical signal series

* Store **signal per hour** (7-day rolling window)
* Enable “signal line” charts
* Keep latest snapshot for fast reads

### 3) On-demand signal recomputation

* Compute EMA in API from hourly data
* Avoid extra storage initially

### 4) Confidence metrics

* Volume-weighted confidence
* Volatility indicators
* Trend strength

---

## Summary

This system intentionally prioritizes:

* correctness
* clarity
* frontend usability
* extensibility

Hourly data provides transparency and charts.
Signal snapshots provide stable UX and scalability.

The architecture is production-grade and ready for incremental intelligence upgrades without breaking APIs or storage contracts.

---