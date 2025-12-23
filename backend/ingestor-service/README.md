# Sentrix Ingestor Service

The **Sentrix Ingestor Service** is responsible for ingesting social media data (starting with Reddit), normalizing it
into a unified event schema, and publishing it to Kafka for downstream processing (sentiment analysis, storage,
analytics, etc.).

At the moment, ingestion is **manually triggered** via a debug API endpoint for testing and validation.
A **scheduler/orchestrator** will be added in a later iteration to automate ingestion runs.

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
│   │   └── (planned: scheduling / orchestration)
  │   │
  │   └── util/
  │       └── (shared utilities)
  │
  └── src/main/resources/
  ├── application.yml
  └── tickers.json
  ```

---

## Current Reddit Ingestion Flow

### Triggering Ingestion

Reddit ingestion is currently triggered manually using a debug endpoint:

  ```
  POST /debug/reddit/run
  ```

This endpoint is intended **only for development and testing**.
A scheduler will be added later to automate ingestion runs.

---

### Data Sources

* **tickers.json**

* Defines tickers and associated search queries
* **Subreddits**

* `stocks`
* `investing`
* `wallstreetbets`
* `options`

---

### Ingestion Steps

For each ticker:

1. Load ticker and queries from `tickers.json`
2. For each subreddit and query:

* Perform subreddit-restricted search (`restrict_sr=1`)
* Normalize raw Reddit JSON into `RedditPost`

3. For each post:

* Deduplicate globally using `post.fullname`
* Map post to `KafkaPostEvent`
* Publish to Kafka
* Fetch comments for the post
* Flatten comment tree into `RedditComment`
* Map comments to `KafkaCommentEvent`
* Publish to Kafka

---

### Deduplication

Posts are deduplicated **globally across all subreddits and queries** using Reddit’s fullname (`t3_xxx`).

This prevents duplicate events caused by:

* overlapping queries
* cross-posts
* repeated ingestion runs

---

### Rate Limiting

A simple in-process rate limiter ensures API calls remain within safe limits and avoids triggering Reddit throttling.

---

## Kafka

### Topic

All events are published to **one Kafka topic**:

  ```
  sentrix.ingestor.events
  ```

### Retention Policy

* `cleanup.policy=delete`
* `retention.ms=604800000` (7 days)

Kafka automatically deletes events older than ~7 days (segment-based cleanup).

---

### Creating the Topic (Local Development)

```
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

  ```
  /opt/homebrew/opt/kafka/bin/kafka-configs \
  --bootstrap-server localhost:9092 \
  --entity-type topics \
  --entity-name sentrix.ingestor.events \
  --describe
  ```

### Delete Topic:

  ```
    /opt/homebrew/opt/kafka/bin/kafka-topics \
    --delete \
    --topic sentrix.ingestor.events \
    --bootstrap-server localhost:9092
  ```
 
Expected values:

* `cleanup.policy=delete`
* `retention.ms=604800000`

---

### Consuming Events (Debug)

```
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
5. Trigger ingestion:

  ```
  curl -X POST http://localhost:8080/debug/reddit/run
  ```

6. Consume from Kafka to verify published events

---

## Next Steps

* Add scheduler/orchestrator for periodic ingestion
* Implement Twitter and Telegram adapters
* Improve retry handling and metrics
* Add monitoring around ingestion runs

---