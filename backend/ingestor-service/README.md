# Sentrix Ingestor Service

The **Sentrix Ingestor Service** is responsible for ingesting social media data (starting with Reddit), normalizing it
into
a unified event schema, and publishing events to Kafka for downstream processing (filtering, sentiment analysis,
storage,
analytics, etc.).

The service currently supports **scheduled ingestion runs** and can also be **manually triggered via a debug endpoint**
for development and validation.

---

## Responsibilities

The ingestor service is responsible for:

* Fetching raw social media data (Reddit)
* Normalizing platform-specific payloads into a unified event schema
* Deduplicating content across queries and subreddits
* Enforcing basic rate limits
* Publishing normalized events to Kafka for downstream consumers

---

## Project Structure

The folder structure below reflects the **current codebase**, with placeholders for future Twitter and Telegram
adapters.

```
ingestor-service/
├── pom.xml
├── README.md
│
├── src/main/java/com/sentrix/ingestor_service/
│   ├── IngestorServiceApplication.java
│   │
│   ├── controller/
│   │   └── RedditDebugController.java
│   │
│   ├── config/
│   │   ├── RedditConfig.java
│   │   ├── TickerConfig.java
│   │   └── TickerConfigLoader.java
│   │
│   ├── adapter/
│   │   ├── reddit/
│   │   │   ├── RedditAdapter.java
│   │   │   ├── client/
│   │   │   │   ├── RedditAuthClient.java
│   │   │   │   └── RedditApiClient.java
│   │   │   ├── mapper/
│   │   │   │   ├── RedditNormalizer.java
│   │   │   │   ├── RedditCommentFlattener.java
│   │   │   │   └── RedditEventMapper.java
│   │   │   └── model/
│   │   │       ├── RedditPost.java
│   │   │       └── RedditComment.java
│   │   │
│   │   ├── twitter/        (planned)
│   │   └── telegram/       (planned)
│   │
│   ├── model/event/
│   │   ├── KafkaEvent.java
│   │   ├── KafkaPostEvent.java
│   │   ├── KafkaCommentEvent.java
│   │   ├── CaptureMeta.java
│   │   ├── EngagementMetrics.java
│   │   ├── PlatformRef.java
│   │   ├── ThreadRef.java
│   │   ├── SourceType.java
│   │   └── EntityType.java
│   │
│   ├── service/
│   │   ├── KafkaEventPublisher.java
│   │   ├── DeduplicationService.java
│   │   ├── RateLimiter.java
│   │   └── RateLimiterRegistry.java
│   │
│   ├── orchestrator/
│   │   └── RedditIngestionScheduler.java
│   │
│   └── util/
│       └── (shared utilities)
│
└── src/main/resources/
    ├── application.yml
    └── tickers.json
```

---

## Reddit Ingestion Flow

### Triggering Ingestion

Reddit ingestion can be triggered in two ways:

1. **Scheduled ingestion (default)**
   A scheduler periodically runs Reddit ingestion automatically.

2. **Manual debug trigger (development only)**

```
POST /debug/reddit/run
```

The debug endpoint is intended **only for development and testing**.

---

### Data Sources

* **tickers.json**

    * Defines tracked tickers and associated search queries

* **Subreddits**

    * `stocks`
    * `investing`
    * `wallstreetbets`
    * `options`

---

### Ingestion Steps

For each ticker:

1. Load ticker configuration from `tickers.json`

2. For each subreddit and query:

    * Perform subreddit-restricted search (`restrict_sr=1`)
    * Normalize raw Reddit JSON into `RedditPost`

3. For each post:

    * Deduplicate globally using Reddit fullname (`t3_xxx`)
    * Map post to `KafkaPostEvent`
    * Publish to Kafka
    * Fetch comments for the post
    * Flatten the comment tree
    * Map comments to `KafkaCommentEvent`
    * Publish to Kafka

---

### Deduplication

Posts are deduplicated **globally across all subreddits and queries** using Reddit’s `fullname`.

This prevents duplicates caused by:

* Overlapping search queries
* Cross-posted content
* Repeated ingestion runs

---

### Rate Limiting

A lightweight in-process rate limiter is used to:

* Keep API usage within safe bounds
* Avoid Reddit throttling
* Smooth bursty ingestion runs

---

## Kafka

### Topic

All ingested events are published to a single Kafka topic:

```
sentrix.ingestor.events
```

---

### Retention Policy

* `cleanup.policy=delete`
* `retention.ms=604800000` (7 days)

Kafka automatically deletes events older than approximately 7 days (segment-based cleanup).

> **Note:**
> The current ingestion window fetches content from the **last 7 days**.
> This may be reduced to a **shorter window (e.g. 1 hour)** in future iterations to support near–real-time pipelines and
> reduce ingestion load.

---

### Creating the Topic (Local Development)

```bash
/opt/homebrew/opt/kafka/bin/kafka-topics \
--create \
--topic sentrix.ingestor.events \
--bootstrap-server localhost:9092 \
--partitions 3 \
--replication-factor 1 \
--config cleanup.policy=delete \
--config retention.ms=604800000
```

---

### Verifying Topic Configuration

```bash
/opt/homebrew/opt/kafka/bin/kafka-configs \
--bootstrap-server localhost:9092 \
--entity-type topics \
--entity-name sentrix.ingestor.events \
--describe
```

Expected values:

* `cleanup.policy=delete`
* `retention.ms=604800000`

---

### Consuming Events (Debug)

```bash
/opt/homebrew/opt/kafka/bin/kafka-console-consumer \
--bootstrap-server localhost:9092 \
--topic sentrix.ingestor.events \
--from-beginning
```

---

## Configuration (`application.yml`)

```yaml
spring:
  kafka:
    bootstrap-servers: localhost:9092
    producer:
      acks: all
      retries: 10
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.apache.kafka.common.serialization.StringSerializer
      properties:
        enable.idempotence: true
        delivery.timeout.ms: 120000
        request.timeout.ms: 30000

reddit:
  client-id: ${CLIENT_ID}
  client-secret: ${CLIENT_SECRET}
  username: ${REDDIT_USERNAME}
  password: ${REDDIT_PASSWORD}
  user-agent: sentrix-ingestor/0.1 by ${REDDIT_USERNAME}
  token-url: https://www.reddit.com/api/v1/access_token
  base-oauth-url: https://oauth.reddit.com

app:
  kafka:
    topic: sentrix.ingestor.events

logging:
  level:
    com.sentrix.ingestor_service.messaging.producer.KafkaEventPublisher: INFO
    com.sentrix.ingestor_service.adapter.reddit: INFO
```

---

## Environment Variables

Before running locally, export:

* `CLIENT_ID`
* `CLIENT_SECRET`
* `REDDIT_USERNAME`
* `REDDIT_PASSWORD`

---

## Running Locally

1. Start Kafka and Zookeeper
2. Create the Kafka topic
3. Export environment variables
4. Run the application
5. (Optional) Trigger ingestion manually:

```bash
curl -X POST http://localhost:8080/debug/reddit/run
```

6. Consume from Kafka to verify published events

---

## Current Status

**Implemented**

* Reddit ingestion
* Scheduled orchestration
* Unified event schema
* Global deduplication
* Kafka publishing
* Rate limiting
* Debug ingestion endpoint

**Pending / Future Work**

* Twitter adapter
* Telegram adapter
* Improved retry and backoff handling
* Expanded test coverage (unit + integration)
* Metrics and ingestion observability
* Configurable ingestion time window

