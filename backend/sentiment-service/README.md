# Sentiment Service

Sentiment Service has two runtime components in the same codebase:
- Worker: consumes filtered events from Kafka, computes hourly aggregates, and updates latest ticker signal snapshots.
- API: serves sentiment data from MongoDB for frontend/backend clients.

## 1) Setup

### 1.1 Prerequisites

- Python 3.12+
- Poetry
- MongoDB Atlas cluster (used in both local and Railway)
- Kafka (local for local runs, Confluent Cloud for Railway runs)

### 1.2 Install dependencies

```bash
cd backend/sentiment-service
poetry install
```

### 1.3 Environment files

- Local: `.env.local` from `.env.local.example`
- Railway: `.env.railway` from `.env.railway.example`
- Mongo stays Atlas in both.

## 2) Sentiment Worker Setup

### 2.1 Local (Worker)

```bash
cd backend/sentiment-service
cp .env.local.example .env.local
# edit .env.local
set -a
source .env.local
set +a
PYTHONPATH=src poetry run python -m sentiment_service.main
```

### 2.2 Railway (Worker)

Railway service config:
- Root directory: `backend/sentiment-service`
- Build command: `poetry install --no-interaction --no-ansi`
- Start command: `PYTHONPATH=src poetry run python -m sentiment_service.main`
- Variables: copy from `.env.railway` (or `.env.railway.example` + real secrets)

## 3) Sentiment API Setup

### 3.1 Local (API)

```bash
cd backend/sentiment-service
cp .env.local.example .env.local
# edit .env.local
set -a
source .env.local
set +a
poetry run uvicorn --app-dir src sentiment_service.api.app:app --host 0.0.0.0 --port 8000
```

Local API base URL:

```text
http://localhost:8000/api/v1
```

### 3.2 Railway (API)

Railway service config:
- Root directory: `backend/sentiment-service`
- Build command: `poetry install --no-interaction --no-ansi`
- Start command: `poetry run uvicorn --app-dir src sentiment_service.api.app:app --host 0.0.0.0 --port $PORT`
- Set `PORT='8080'`
- Variables: copy from `.env.railway` (or `.env.railway.example` + real secrets)

## 4) Data Flow and Architecture

Pipeline flow:
1. Filtering Service B publishes cleaned events to Kafka topic `sentrix.filter-service-b.filtered`.
2. Sentiment worker consumes that topic.
3. Each event is parsed from envelope shape (`ingestorEvent`, `textView`, `filterMeta`).
4. Worker computes per-event sentiment (currently stub scorer), extracts keywords, and increments hourly aggregate documents in MongoDB.
5. Background signal loop computes and upserts one latest signal document per ticker for the latest eligible closed hour.
6. API reads MongoDB only and serves frontend/backend clients.

Why two Mongo collections:
- `ticker_sentiment_hourly`: raw hourly series for charts, transparency, recomputation.
- `ticker_sentiment_signal`: one latest snapshot per ticker for cheap low-latency reads.

This separation keeps chart reads accurate and signal reads fast.

## 5) API Endpoints

Base prefix:

```text
/api/v1
```

### 5.1 `GET /api/v1/health`

Purpose:
- Liveness check.

Response:

```json
{ "ok": true }
```

### 5.2 `GET /api/v1/tickers`

Purpose:
- List recent tickers from hourly aggregates.

Query params:
- `limit` (optional, default `2000`, min `1`, max `20000`)

Response shape:

```json
{
  "tickers": ["AAPL", "TSLA", "MSFT"],
  "count": 3
}
```

Notes:
- `tickers` is sliced by `limit`.
- `count` is total distinct recent tickers before slicing.

### 5.3 `POST /api/v1/signals/latest`

Purpose:
- Batch fetch latest signal docs for many tickers.

Request body:

```json
{
  "tickers": ["AAPL", "TSLA", "MSFT"]
}
```

Validation:
- Empty `tickers` list returns `400`.

Response shape:

```json
{
  "requested": ["AAPL", "TSLA", "MSFT"],
  "found": 2,
  "signals": {
    "AAPL": {
      "_id": "AAPL",
      "ticker": "AAPL",
      "signalScore": 0.42,
      "asOfHourStartUtc": 1774584000,
      "updatedAtUtc": 1774587600
    },
    "TSLA": {
      "_id": "TSLA",
      "ticker": "TSLA",
      "signalScore": -0.10,
      "asOfHourStartUtc": 1774584000,
      "updatedAtUtc": 1774587600
    }
  }
}
```

### 5.4 `GET /api/v1/tickers/{ticker}/sentiment`

Purpose:
- Ticker detail endpoint for chart + latest signal.

Query params:
- `hours` (optional, default `48`, min `1`, max `336`)

Response shape:

```json
{
  "ticker": "TSLA",
  "signal": {
    "_id": "TSLA",
    "ticker": "TSLA",
    "signalScore": 0.35,
    "asOfHourStartUtc": 1774584000,
    "updatedAtUtc": 1774587600
  },
  "hourly": [
    {
      "_id": "TSLA|1774580400",
      "ticker": "TSLA",
      "hourStartUtc": 1774580400,
      "hourEndUtc": 1774583999,
      "count": 18,
      "scoreSum": 4.3,
      "keywordCounts": {"delivery": 3, "earnings": 2},
      "sourceBreakdown": {"REDDIT": 18},
      "updatedAtUtc": 1774584100,
      "expireAtUtc": 1775188799
    }
  ]
}
```

Error case:
- If both signal and hourly data are missing for the ticker, returns `404`.

## 6) Storage Model

### 6.1 `ticker_sentiment_hourly`

Purpose:
- Event-driven hourly aggregation store.

Behavior:
- One doc per `(ticker, hour)` with `_id = {ticker}|{hourStartUtc}`.
- Updated via `$inc` so streaming writes are replay-friendly and do not require read-before-write.
- TTL via `expireAtUtc` + TTL index (rolling retention).

Primary fields:
- `_id`, `ticker`, `hourStartUtc`, `hourEndUtc`
- `count`, `scoreSum`
- `keywordCounts`, `sourceBreakdown`
- `updatedAtUtc`, `expireAtUtc`

### 6.2 `ticker_sentiment_signal`

Purpose:
- Serving snapshot store.

Behavior:
- One doc per ticker (`_id = ticker`).
- Updated only when the new hour is strictly newer than existing `asOfHourStartUtc`.
- Prevents duplicate same-hour signal application.

Primary fields:
- `_id`, `ticker`, `signalScore`
- `asOfHourStartUtc`, `updatedAtUtc`
- optional future fields: `recentVolume`, `keywords`, `halfLifeHours`

## 7) What Is Implemented

- Kafka consumer for cleaned events (`sentrix.filter-service-b.filtered`)
- Envelope parsing from filter output
- Stub sentiment scoring + keyword extraction
- Incremental hourly aggregation into Mongo
- TTL-managed hourly retention
- Periodic signal updater loop
- Latest signal upsert with per-hour idempotency guard
- FastAPI serving layer with health/tickers/signals/detail endpoints

## 8) Not Implemented Yet (Planned)

- Real sentiment model (currently stub)
- Historical signal series storage (only latest snapshot stored)
- Advanced signal features (confidence, volatility, trend strength)
- richer API-level analytics endpoints

## 9) Quick API Test Commands

```bash
# health
curl http://localhost:8000/api/v1/health

# ticker list
curl "http://localhost:8000/api/v1/tickers?limit=50"

# latest signals
curl -X POST http://localhost:8000/api/v1/signals/latest \
  -H 'Content-Type: application/json' \
  -d '{"tickers":["TSLA","AAPL","MSFT"]}'

# ticker detail
curl "http://localhost:8000/api/v1/tickers/TSLA/sentiment?hours=48"
```
