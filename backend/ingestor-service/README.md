# Sentrix Ingestor Service

The Sentrix Ingestor Service fetches social data (currently Reddit), normalizes it into a unified event schema, and publishes events to Kafka for downstream services.

## Common Setup

### 1) Prerequisites

- Java 21
- Maven wrapper (`./mvnw` is included)
- Kafka topic ready (local Kafka or Confluent Cloud)

Set Java 21 in terminal:

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@21
export PATH="$JAVA_HOME/bin:$PATH"
java -version
```

### 2) Environment File Templates

Available env files:
- local runtime: `backend/ingestor-service/.env.local`
- Railway runtime: `backend/ingestor-service/.env.railway`
- examples:
  - `backend/ingestor-service/.env.local.example`
  - `backend/ingestor-service/.env.railway.example`

## Local Setup

### 1) Environment Variables

Set Java 21 in the current terminal session first:

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@21
export PATH="$JAVA_HOME/bin:$PATH"
java -version
```

Use local env values:

```bash
cd backend/ingestor-service
cp .env.local.example .env.local
```

Required Reddit variables:
- `CLIENT_ID`
- `CLIENT_SECRET`
- `REDDIT_USERNAME`
- `REDDIT_PASSWORD`

Optional Reddit search controls:
- `REDDIT_SEARCH_TIME_FILTER` (`hour|day|week|month|year|all`, default `week`)
- `REDDIT_SEARCH_LIMIT` (default `50`)
- `REDDIT_SEARCH_SORT` (default `new`)

For local Kafka:
- `KAFKA_BOOTSTRAP_SERVERS=localhost:9092`
- `KAFKA_SECURITY_PROTOCOL=PLAINTEXT`
- leave SASL vars empty

Runtime variable:
- `PORT` (default `8080`)

Optional scheduler controls:
- `INGESTION_SCHEDULER_CRON` (default `0 0 * * * *`)
- `INGESTION_SCHEDULER_ZONE` (default `UTC`)

### 2) Kafka Topic

Topic used by this service:

- `sentrix.ingestor.events`

Recommended topic policy:

- `cleanup.policy=delete`
- `retention.ms=604800000` (7 days)

### 3) Run Locally

```bash
cd backend/ingestor-service
set -a; source .env.local; set +a
./mvnw spring-boot:run
```

Note: Spring Boot does not auto-load `.env` files by default. `source .env.local` is required unless your IDE run config injects env vars.

### 4) Trigger a Manual Ingestion Run

```bash
curl -X POST http://localhost:8080/debug/reddit/run
```

## Railway Setup

### 1) Environment Variables

Use `backend/ingestor-service/.env.railway` values in Railway Variables.

For Railway + Confluent Cloud:

```env
KAFKA_BOOTSTRAP_SERVERS=<pkc-xxxxx...:9092>
KAFKA_TOPIC=sentrix.ingestor.events
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_JAAS_CONFIG=org.apache.kafka.common.security.plain.PlainLoginModule required username="<API_KEY>" password="<API_SECRET>";
```

If logs show `localhost:9092`, Railway vars are missing or not applied and service is using defaults.

### 2) Railway Deployment (Monorepo)

Use one Railway service for this microservice, with this monorepo path:

- Root directory: `backend/ingestor-service`
- Build command: `./mvnw -DskipTests package`
- Start command: `java -jar target/*.jar`

Set the same Reddit vars as local, but Kafka vars from `.env.railway`.

Use HTTPS and POST for manual trigger:

```bash
curl -X POST https://<your-railway-domain>/debug/reddit/run
```

## Configuration Reference

Current app config file:

- `src/main/resources/application.yml`

Key runtime bindings:

- `spring.kafka.bootstrap-servers -> KAFKA_BOOTSTRAP_SERVERS`
- `spring.kafka.producer.properties.security.protocol -> KAFKA_SECURITY_PROTOCOL`
- `spring.kafka.producer.properties.sasl.mechanism -> KAFKA_SASL_MECHANISM`
- `spring.kafka.producer.properties.sasl.jaas.config -> KAFKA_SASL_JAAS_CONFIG`
- `app.kafka.topic -> KAFKA_TOPIC`
- `reddit.search-time-filter -> REDDIT_SEARCH_TIME_FILTER`
- `reddit.search-limit -> REDDIT_SEARCH_LIMIT`
- `reddit.search-sort -> REDDIT_SEARCH_SORT`
- `ingestion.scheduler.cron -> INGESTION_SCHEDULER_CRON`
- `ingestion.scheduler.zone -> INGESTION_SCHEDULER_ZONE`
- `server.port -> PORT`

## Architecture and Design Justifications

### Unified Event Schema Contract

All source-specific payloads are mapped into a shared `KafkaEvent` contract before publishing.

Core fields include:

- identity and traceability: `eventVersion`, `eventId`, `dedupKey`
- timing: `createdAtUtc`, `ingestedAtUtc`
- routing context: `source`, `entityType`, `ticker`, `community`
- content: `title`, `text`, `contentUrl`, `author`
- platform/thread metadata: `platform`, `thread`
- analytics context: `metrics`, `capture`, `lang`

Why this schema is strong:

- downstream services consume one stable shape instead of per-platform JSON
- adding new sources does not break consumer contracts
- `eventVersion` gives room for safe schema evolution
- `capture` keeps query/fetch provenance for audit and evaluation
- `platform` and `thread` preserve enough source detail for later enrichment

### Adapter-Based Source Abstraction

Ingestion is built around the `SocialSourceAdapter` interface:

- `source()`
- `runIngestion()`

Current Reddit implementation plugs into this interface, and future Twitter/Telegram adapters can implement the same contract.

Why this abstraction matters:

- open/closed design: new platforms added with minimal orchestrator changes
- each source keeps platform-specific API logic isolated in its adapter/client/mapper layer
- shared orchestration, publishing, and observability stay consistent across all sources

### Mapping Layer Separation

`RedditEventMapper` converts normalized Reddit models into `KafkaPostEvent` / `KafkaCommentEvent`.

Why this separation is useful:

- isolates transformation logic from API fetching logic
- keeps schema guarantees in one place
- easier to unit test mapping correctness independently

### Orchestration and Concurrency Model

`IngestionOrchestrator` discovers all adapters and runs them via a dedicated executor.
It also prevents overlapping runs using an atomic `running` guard and applies adapter-level timeouts.

Why this design was chosen:

- supports multi-source parallelism
- prevents accidental overlap when runs are long
- keeps scheduling policy separate from source logic

### Deduplication Strategy

Deduplication uses stable Reddit fullname IDs through `DeduplicationService` (`ConcurrentHashMap`-backed set).

Why:

- cheap, deterministic duplicate removal across overlapping queries/subreddits
- protects downstream stages from duplicated sentiment signal inflation

### Rate Limiting via Registry

`RateLimiterRegistry` holds per-source limiters (e.g., Reddit/Twitter/Telegram limits) and adapters acquire permits before calls.

Why this is effective:

- one central place to manage per-source throttling policy
- avoids scattering sleep/retry timing logic across code
- protects ingestion from API throttling/burst failures

Note: limits are currently set in code in the registry constructor and can be externalized to config later without changing adapter usage.

## Operational Rules and Justifications

### Ingestion Triggers

- Scheduled ingestion runs every hour (UTC).
- Manual endpoint (`POST /debug/reddit/run`) exists for development validation.

Why:

- Scheduler keeps automated ingestion cadence.
- Manual trigger speeds up test/debug cycles.

### Data Scope

- Source: Reddit (currently)
- Subreddits: `stocks`, `investing`, `wallstreetbets`, `options`
- Tickers/queries loaded from `tickers.json`

Why:

- Controlled scope improves signal quality and keeps ingestion costs bounded.

### Deduplication Rule

- Post dedup uses Reddit fullname globally across queries/subreddits/runs.

Why:

- Prevents duplicate event inflation from overlapping queries and repeated scans.

### Publishing Rule

- All normalized events go to one topic: `sentrix.ingestor.events`.

Why:

- Keeps downstream contract simple for Filter A and other consumers.

### Retention Rule

- 7-day topic retention (`retention.ms=604800000`).

Why:

- Preserves enough replay/debug window without unbounded storage growth.

## Project Structure

```text
ingestor-service/
├── pom.xml
├── README.md
├── .env.local.example
├── .env.railway.example
├── src/main/java/com/sentrix/ingestor_service/
│   ├── adapter/reddit/
│   ├── config/
│   ├── controller/
│   ├── messaging/
│   ├── orchestrator/
│   └── service/
└── src/main/resources/
    ├── application.yml
    └── tickers.json
```

## Current Status

Implemented:

- Reddit ingestion
- Scheduled orchestration
- Manual debug trigger endpoint
- Unified event mapping
- Global deduplication
- Kafka publishing
- Basic rate limiting

Pending:

- Twitter adapter
- Telegram adapter
- Expanded tests and observability
- More configurable ingestion policies
