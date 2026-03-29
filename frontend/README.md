# Sentrix Frontend

Next.js frontend for Sentrix. It combines:
- TradingView market/stock widgets for market context.
- Sentrix API data for sentiment monitor + sentiment analytics.
- Finnhub-backed stock/news search.

## Setup

### Local setup

1. Install prerequisites:
   - Node.js 20+
   - npm
2. Go to frontend folder:
```bash
cd frontend
```
3. Install dependencies:
```bash
npm install
```
4. Create local env from example:
```bash
cp .env.example .env
```
5. Set required values in `.env`:
```env
NODE_ENV='development'
FINNHUB_API_KEY='<YOUR_FINNHUB_API_KEY>'
FINNHUB_BASE_URL='https://finnhub.io/api/v1'
NEXT_PUBLIC_SENTRIX_API_BASE_URL='http://localhost:8000/api/v1'
```
6. Run:
```bash
npm run dev
```
7. Open `http://localhost:3000`.

### Railway setup

1. Deploy `frontend/` as the Railway service root.
2. Set Railway variables using `.env.railway.example` as template:
```env
NODE_ENV='production'
FINNHUB_API_KEY='<YOUR_FINNHUB_API_KEY>'
FINNHUB_BASE_URL='https://finnhub.io/api/v1'
NEXT_PUBLIC_SENTRIX_API_BASE_URL='https://sentiment-api-production-c71c.up.railway.app/api/v1'
```
3. Use:
   - Build command: `npm run build`
   - Start command: `npm run start`
4. Ensure `NEXT_PUBLIC_SENTRIX_API_BASE_URL` is `https://...` in Railway to avoid browser mixed-content blocks.

## Tech Stack

- Next.js 15 + React 19 + TypeScript
- Tailwind CSS + shadcn/ui
- TradingView embedded widgets
- Recharts (sentiment time-series chart)
- Finnhub API (stock search + market news)

## What Is Implemented

### Dashboard

- TradingView widgets on home page:
  - Market Overview
  - Timeline / Top Stories
  - S&P500 Heatmap
- Custom Sentiment Monitor widget:
  - Pulls tickers from Sentrix API
  - Fetches latest signal snapshot per watchlist ticker
  - Polls on fixed 5-minute boundary schedule
  - Shows score, label (Bullish/Neutral/Bearish), and top keywords

### Stock details

- Per-symbol page embeds TradingView widgets:
  - Symbol info
  - Advanced candlestick chart
  - Baseline chart
  - Technical analysis
  - Company profile
  - Company financials

### Sentiment analytics

- `/analytics` page fetches hourly sentiment series from Sentrix API.
- Supports 12H / 1D / 2D / 7D ranges.
- Uses Recharts line chart with:
  - bullish/neutral/bearish background zones
  - average sentiment line
  - post-volume in tooltip

### Search and news

- Server-side Finnhub integration:
  - ticker search
  - market/company news aggregation
- Header preloads popular symbols and supports command-style stock search.

## Sentrix API Usage

Frontend calls these endpoints via `NEXT_PUBLIC_SENTRIX_API_BASE_URL`:

- `GET /tickers?limit=...`
- `POST /signals/latest`
- `GET /tickers/{ticker}/sentiment?hours=...`

The frontend is read-only for sentiment data; writing/aggregation is done by backend services.
