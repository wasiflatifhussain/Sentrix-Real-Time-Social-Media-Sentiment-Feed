# Sentrix Filtering Service A

Filtering Service A is the first hard-gate in the Sentrix pipeline.
It consumes ingestor events, applies deterministic filtering/normalization, and routes each event to cleaned vs dropped topics.

## What This Service Does

Input topic:
- `sentrix.ingestor.events`

Output topics:
- `sentrix.filter-service-a.cleaned` (`KEEP`)
- `sentrix.filter-service-a.dropped` (`DROP`)

Core responsibilities:
- validate minimum event integrity
- normalize text and build deterministic text features
- drop clearly invalid / low-quality events
- perform exact dedup checks (ID + content hash)
- add near-dup wave metadata for downstream services

Non-goals:
- sentiment scoring
- semantic relevance/credibility ranking (handled downstream by Filter B)

## Tech Stack

- Java 21
- Spring Boot 4
- Spring Kafka
- Spring Data Redis (Lettuce)
- Maven wrapper (`./mvnw`)

## Setup and Configuration

### Config files and env files

Main config file:
- `src/main/resources/application.yml`

Recommended env files:
- Local development: `backend/filtering-service-a/.env.local`
- Railway deployment reference: `backend/filtering-service-a/.env.railway`
- Templates:
  - `backend/filtering-service-a/.env.local.example`
  - `backend/filtering-service-a/.env.railway.example`

Important:
- Spring Boot does not auto-load shell `.env` files.
- For local terminal runs, export values first (`set -a; source ...; set +a`).

### Local setup

1. Prerequisites
- Java 21
- Kafka reachable from local machine
- Redis reachable from local machine

2. Set Java 21 (macOS Homebrew example)

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@21
export PATH="$JAVA_HOME/bin:$PATH"
java -version
```

3. Run locally

```bash
cd backend/filtering-service-a
set -a
source .env.local
set +a
./mvnw spring-boot:run
```

4. Confirm env loaded

```bash
env | egrep '^(KAFKA_|APP_KAFKA_|REDIS_|PORT)'
```

### Railway setup

Monorepo service settings:
- Root Directory: `backend/filtering-service-a`
- Build Command: `./mvnw -DskipTests package`
- Start Command: `java -jar target/*.jar`

Use values from `.env.railway` in Railway Variables.

Redis host rule:
- Inside Railway deployment: use internal host (for example `redis.railway.internal:6379`).
- From local machine: use Railway public Redis host+port (proxy endpoint), not internal host.

### Kafka topics and retention

Service A reads:
- `APP_KAFKA_TOPIC_RAW` (default `sentrix.ingestor.events`)

Service A writes:
- `APP_KAFKA_TOPIC_CLEANED` (default `sentrix.filter-service-a.cleaned`)
- `APP_KAFKA_TOPIC_DROPPED` (default `sentrix.filter-service-a.dropped`)

Consumer group:
- `APP_KAFKA_CONSUMER_GROUP_ID` (default `filter-service-a`)

Target retention policy:
- 7 days (`retention.ms=604800000`) for Service A output topics.

Create output topics with 7-day retention:

```bash
kafka-topics --bootstrap-server <BOOTSTRAP> --create --if-not-exists \
  --topic sentrix.filter-service-a.cleaned \
  --partitions 3 --replication-factor 1 \
  --config retention.ms=604800000

kafka-topics --bootstrap-server <BOOTSTRAP> --create --if-not-exists \
  --topic sentrix.filter-service-a.dropped \
  --partitions 3 --replication-factor 1 \
  --config retention.ms=604800000
```

If topics already exist, enforce 7-day retention:

```bash
kafka-configs --bootstrap-server <BOOTSTRAP> --alter --entity-type topics \
  --entity-name sentrix.filter-service-a.cleaned \
  --add-config retention.ms=604800000

kafka-configs --bootstrap-server <BOOTSTRAP> --alter --entity-type topics \
  --entity-name sentrix.filter-service-a.dropped \
  --add-config retention.ms=604800000
```

### Kafka security (Confluent Cloud)

Required when using Confluent Cloud:
- `KAFKA_SECURITY_PROTOCOL=SASL_SSL`
- `KAFKA_SASL_MECHANISM=PLAIN`
- `KAFKA_SASL_JAAS_CONFIG=org.apache.kafka.common.security.plain.PlainLoginModule required username="<API_KEY>" password="<API_SECRET>";`

## Runtime Architecture

Pipeline shape:
- Kafka consumer (manual ack)
- deterministic filtering pipeline (ordered stages)
- Kafka producer to cleaned/dropped topics
- Redis state for dedup and near-dup memory

Reliability behavior:
- offsets are acknowledged only after publish succeeds
- malformed/unparseable input is routed to dropped and acknowledged (poison-pill fail-safe)

## What Service A Adds to Each Event

Instead of redefining the full ingestor contract, Service A adds a filtering envelope around it:

- `ingestorEvent`: original incoming event
- `filterMeta`: decision and filtering metadata
  - `decision`: `KEEP` or `DROP`
  - `dropReason` / rule reason when dropped
  - timestamps and rule tags/signals used in filtering
- `textView`: normalized/canonical text representation
  - normalization outputs (cleaned text, truncation flags)
- `eventFeatures`: deterministic feature counts/signals
  - url count, emoji count, cashtag count, repeated-char indicators, etc.

This is what downstream services consume as the filtered artifact.

## Filtering Stages and Why They Exist

### Stage 1: baseline integrity checks

What it does:
- confirms required structural fields are present and minimally valid

Why it exists:
- invalid structure cannot be recovered downstream; fail early keeps the stream healthy

### Stage 2: normalization and feature extraction

What it does:
- builds canonical text view
- computes deterministic text features used by later rules

Why it exists:
- dedup and rule checks require stable, comparable text
- deterministic features are cheap, explainable, and fast

### Stage 3: hard validation rules

What it does:
- enforces bounds like minimum text length, event age window, truncation policy

Why it exists:
- removes stale/invalid records before they consume downstream resources

### Stage 4: exact dedup

What it does:
- ID dedup (`dedup:id:*`)
- content hash dedup (`dedup:hash:*`) with TTL/time bucketing

Why it exists:
- catches retries and exact reposts with high precision and low cost

### Stage 5: deterministic heuristic drops

What it does:
- applies conservative high-confidence drop rules (spam-like URL density, repeated chars, excessive emoji/cashtags)

Why it exists:
- removes obvious junk without introducing black-box behavior

### Stage 6: near-dup wave detection (metadata)

What it does:
- uses SimHash + Hamming distance against recent fingerprints in Redis buckets
- flags copy-wave patterns in metadata

Why it exists:
- preserves recall (often still KEEP) while surfacing repetition patterns for downstream ranking/relevance

## Redis Usage Notes

Redis stores short-lived state for:
- ID/content-hash dedup windows
- near-dup fingerprint buckets

Fail-open behavior:
- if Redis is unavailable, warnings are logged and affected checks degrade
- service continues processing to avoid full stream stoppage

## Useful Commands

Run unit tests:

```bash
cd backend/filtering-service-a
./mvnw test
```

Build jar:

```bash
cd backend/filtering-service-a
./mvnw -DskipTests package
```

Run app locally (after env export):

```bash
cd backend/filtering-service-a
./mvnw spring-boot:run
```
