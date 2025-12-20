# Reddit Social Media Ingestion POC

## Overview

This proof-of-concept (POC) implements a **Reddit data ingestion pipeline** designed to collect social media discussions related to publicly listed companies. The goal is to simulate the **ingestion stage of a microservices-based data platform**, where raw social data is collected, normalized, and prepared for downstream processing such as filtering, sentiment analysis, and machine learning.

This POC focuses on **recall, correctness, and architectural clarity**, rather than semantic understanding, which is handled later in the pipeline.

---

## Stock Selection

The system tracks **20 large, high-market-cap companies**, chosen to ensure:

- consistent discussion volume on Reddit,
- relevance to financial markets,
- a realistic but manageable scope for an FYP.

Each stock is defined in a configuration file (`tickers.json`) containing:

- the stock ticker (e.g. `TSLA`, `AAPL`),
- the company name,
- **4 predefined search queries**.

### Query Design

For each stock, four queries are used to balance recall and precision:

1. Cashtag-based query (e.g. `$TSLA`)
2. Ticker + finance keywords (e.g. `TSLA stock`)
3. Company name + stock (e.g. `Tesla stock`)
4. Earnings-related query (e.g. `TSLA earnings OR Tesla earnings`)

This ensures the system captures:

- formal financial discussions,
- informal retail-investor mentions,
- posts that avoid ticker symbols.

---

## Subreddit Scope

Searches are performed across **four finance-focused subreddits**:

- `r/stocks`
- `r/investing`
- `r/wallstreetbets`
- `r/options`

These subreddits were chosen because they represent:

- long-term investing discussions,
- short-term trading sentiment,
- options-related market activity.

Searches are restricted to these subreddits to maintain **topic relevance** and reduce noise.

---

## Data Collection Process

For each stock:

1. The system executes subreddit-based searches using the configured queries.
2. Reddit search results are retrieved for a **weekly time window** (`t = "week"`) to ensure sufficient coverage.
3. Raw Reddit API responses are normalized into a simplified internal format.

---

## Deduplication Strategy

Because the same Reddit post can match multiple queries or appear multiple times:

- **posts are deduplicated using their Reddit fullname (`t3_xxx`)**,
- each unique post is processed exactly once,
- comments are fetched **only once per unique post**.

This prevents:

- duplicate events,
- redundant API calls,
- inflated datasets.

---

## Event-Based Data Model

All data is converted into **event objects**, following an event-streaming mindset.

### Post Events

Each Reddit post becomes a **post event**, containing:

- stock ticker,
- subreddit,
- title and body text,
- author and score,
- creation timestamp,
- query metadata used to retrieve it.

### Comment Events

Each Reddit comment is emitted as a **separate comment event**, linked to:

- its parent comment (if any),
- its root post.

This ensures:

- comments are first-class data entities,
- conversation structure can be reconstructed later,
- downstream services can analyze posts and comments independently.

---

## Output Format

Events are written to disk in **JSON Lines (`.jsonl`) format**, where:

- each line represents one event,
- events are independent and stream-friendly,
- the format mirrors how data would later be sent to Kafka.

This makes the output:

- easy to inspect,
- resilient to partial failures,
- directly compatible with streaming systems.

---

## Rate Limiting

To comply with Reddit’s free-tier API limits:

- a **global rate limiter** is enforced,
- the system allows a maximum of **100 API calls per minute**,
- all Reddit API calls (search and comments) pass through the limiter.

This ensures:

- no API throttling or bans,
- predictable ingestion runtime,
- realistic operational constraints.

---

## Scope and Limitations

This POC intentionally focuses on:

- data ingestion,
- normalization,
- deduplication,
- event construction.

It does **not** perform:

- sentiment analysis,
- relevance classification,
- language translation,
- spam filtering.

These responsibilities are deferred to **downstream microservices**, following a clean separation of concerns.

---

## Purpose

This POC serves as:

- a foundation for a larger microservices-based social data pipeline,
- a realistic demonstration of ingestion-layer design,
- a basis for later integration with Kafka and Spring Boot services.

---

If you want, next I can:

- tighten this README into a more **academic tone**, or
- help you write the **architecture / system design section** of your FYP using this POC as the ingestion layer.
