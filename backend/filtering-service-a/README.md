# Filtering Service A — Fast Filtration & Cleaning (Hard Gate)

## 1) Development plan: build in the right order

### Phase 0 — Lock the contract (1–2 hours)

**Goal:** Define the exact event contract *and* what Service A guarantees.

#### 0.1 Decide the **input Event contract**

We will **reuse the ingestor’s `KafkaEvent` contract** (no schema fork).

Minimum fields Service A expects to be present (required for “KEEP”):

* `eventId` (or `dedupKey`)
* `source`
* `entityType` (POST/COMMENT/etc.)
* time: at least one of `createdAtUtc` or `ingestedAtUtc`
* content: at least one meaningful text field (`text`, and optionally `title`)
* `ticker` (strongly recommended; required if your pipeline is ticker-based)

Other fields are optional and passed through unchanged:

* `community`, `author`, `platform`, `thread`, `metrics`, `capture`, `lang`, etc.

#### 0.2 Decide the **output contract**

Service A outputs **two Kafka topics**:

* `events.cleaned`: events that are **sanitized + enriched** and **not obviously broken/garbage**
* `events.dropped`: events that failed **hard-gate** checks (kept for auditing + evaluation)

Important clarification:

> “cleaned” does **not** mean “safe/verified/approved for sentiment”.
> It only means “passed hard-gate checks (schema + obvious junk) and has normalization/features attached”.

#### 0.3 Decide how Service A attaches metadata

Service A must attach the following metadata (for both kept and dropped events):

* `filterStage = "hard_gate_A"`
* `filterReasons[]` (non-empty for DROPPED; may be empty for KEPT)
* `textNorm`
* extracted features (counts/domains/etc.)

Implementation note (contract-level only):
Prefer **wrapping** the original `KafkaEvent` inside an “envelope” message that includes these metadata fields, so the
base event contract stays stable across services.

#### 0.4 Runtime guarantee (very explicit)

Each incoming event passes through the entire Service A pipeline **once**.
Only after all steps run, Service A makes a final decision:

* **KEEP** → publish once to `events.cleaned`
* **DROP** → publish once to `events.dropped`

✅ Don’t start implementing logic until this contract is written down, or you’ll rewrite everything.

---

### Phase 1 — Spring skeleton + Kafka IO (foundation)

**Goal:** Service runs end-to-end: consume raw events from Kafka, publish processed envelopes to Kafka, and commit
offsets only after publish succeeds.

Build in this order:

1. **Create Spring Boot app:** `filtering-service-a`

2. **Configure Kafka + app topics**

    * `application.yml` for:

        * `spring.kafka.bootstrap-servers`
        * consumer group id
        * producer reliability settings (acks=all, retries, idempotence)
    * `app.kafka.topic.*` for:

        * `raw` (input)
        * `cleaned` (output KEEP)
        * `dropped` (output DROP)
    * env vars:

        * `KAFKA_BOOTSTRAP_SERVERS` (default local)

3. **Implement Kafka consumer (manual ack)**

    * `@KafkaListener(topics=${app.kafka.topic.raw}, groupId=${app.kafka.consumer.group-id})`
    * Use **manual acknowledgment** (`AckMode.MANUAL`)
    * Add lightweight heartbeat logging (every N messages) to verify liveness and partition progress.

4. **Implement Kafka producer wrapper**

    * Publish a JSON envelope to:

        * `events.cleaned` for `KEEP`
        * `events.dropped` for `DROP`
    * Attach Kafka headers for traceability:

        * `source`, `entityType`, `decision`, `filterReason`
    * **Ack only after publish success**:

        * `kafkaTemplate.send(...).thenRun(ack::acknowledge)`
        * if publish fails, do not ack (so Kafka can retry delivery)

5. **Implement Phase 1 “Hard Gate” pipeline**

    * Minimal checks that indicate broken/unusable inputs:

        * null event
        * missing both `eventId` and `dedupKey`
        * missing `source`
        * missing `entityType`
        * empty combined text (`title + text`)
    * Everything else is temporary pass-through:

        * return `KEEP` with a basic envelope (no normalization/features yet)

6. **Structured logging for audit/debug**

    * Log at decision points:

        * `source`, `entityType`, `key`, `eventId`, `decision`, `filterReason`, topic/partition/offset
    * Log parse failures separately (`RAW_PARSE_FAIL`) and route them to `events.dropped`.

✅ **End of Phase 1**

* Service consumes from `events.raw`
* Produces `KEEP` → `events.cleaned`, `DROP` → `events.dropped`
* Offsets commit only after output publish succeeds
* Pass-through behavior is effectively **KEEP most events**, while **definitely broken** events are dropped with
  explicit reasons

---

### Phase 2 — Canonicalization & feature extraction (always before rules)

**Goal:** For every event that survives the hard gate, compute `textNorm` and cheap features for downstream rules + ML.

Build in this order:

1. **Add `Normalizer` component**

    * Input: raw `title + text`
    * Output: `NormalizedText`:

        * `textNorm`
        * `wasTruncated` (if you enforce max length)
        * `originalLength`
    * Normalization steps:

        * replace URLs → `<URL>`
        * normalize cashtags (consistent format/case)
        * whitespace cleanup

2. **Add `FeatureExtractor`**

    * Extract:

        * urls/domains/mentions/cashtags/hashtags
    * Compute counts:

        * word count
        * url_count
        * emoji_count
        * caps_ratio
        * repeated-char score

3. **Update the envelope**

    * Add `textView.textNormalized = textNorm`
    * Add `eventFeatures = features`
    * Preserve original raw event untouched

✅ **End of Phase 2**

* `events.cleaned` messages carry:

    * original raw event
    * `textNorm`
    * extracted features

---

### Phase 3 — Schema validation + hard failures (DROP only “definitely broken”)

**Goal:** Drop only events that cannot be used reliably (not “suspicious” content).

Build:

1. **Add `Validator`**

    * Runs after normalization + feature extraction
    * Examples (config-driven):

        * missing required fields → `DROP`
        * empty/too-short normalized text → `DROP`
        * too old → `DROP` or `KEEP + tag` (choose one policy)
        * oversize handling → truncate + mark `OVERSIZE_TRUNCATED` (or drop if absurd)

2. **Reason codes**

    * `MISSING_FIELD`
    * `EMPTY_TEXT`
    * `TOO_OLD`
    * `OVERSIZE_TRUNCATED`

✅ **End of Phase 3**

* Service A drops only clearly unusable events (with explainable reasons)
* Dropped events go to `events.dropped` for audit/evaluation

---

Yes — **what you said is correct**, and it’s an important clarification:

> **The bucket is primarily to catch duplicates caused by overlapping queries and ingestion artifacts within the same
short time window — not to deduplicate content across the entire 7-day lookback.**

Below is a **concise README section** that makes this explicit and easy to remember.

---

## Phase 4 — Exact Deduplication (ID + Content Hash)

Service A performs **exact deduplication** to remove ingestion-level noise while preserving legitimate repeated
discussion.

### Dedup mechanisms

1. **Event ID dedup**

    * Drops events with the same `dedupKey`
    * Handles API retries, restarts, and duplicate object ingestion

2. **Content dedup (time-bucketed)**

    * Drops events with identical `(source, normalized text, ticker)` **within a short time window**
    * Implemented by hashing:

   ```
   source | normalized_text | ticker | time_bucket
   ```

   where:

   ```
   time_bucket = event_epoch_seconds / bucket_seconds
   ```

### Why time buckets are needed

Time buckets define **when two contents are considered duplicates**.

The primary purpose is **not** to deduplicate content across the entire lookback window (e.g. 7 days), but to catch
duplicates caused by:

* overlapping queries for the same ticker (e.g. `$TSLA`, `Tesla`, sector queries)
* pagination overlap and API retries
* ingestion artifacts within the same run or adjacent runs

Without buckets, identical content would be suppressed for the full TTL period, incorrectly removing legitimate reposts
and follow-up discussion.

### Why Redis TTL is still required

Redis TTL controls **how long dedup state is remembered**, not **what is considered a duplicate**.

* TTL prevents unbounded memory growth
* Time buckets limit deduplication to short, ingestion-relevant windows

Both are required to avoid over-deduplication.

---

### Phase 5 — Heuristic spam/scam rules (cheap wins, DROP only slam-dunks)

**Goal:** Remove only obvious spam/scams without ML.

Build:

1. **Rule engine**

    * `FilterRule` interface
    * Each rule returns:

        * matched? (yes/no)
        * action: DROP/KEEP
        * reason code(s)

2. **Rules in sensible order**

    * absurd URL spam (very high url_count)
    * denylist domains (high-confidence malicious)
    * scam phrase regex (high precision)
    * extreme emoji / repeated chars (only slam-dunks)
    * too many tickers/cashtags (if multi-ticker later)

3. **Config-driven thresholds**

    * `maxUrls`, `minWords`, etc.

✅ **End of Phase 5**

* Obvious junk removed; borderline content preserved for Service B

---

### Phase 6 — Near-duplicate fingerprinting (KEEP but tag)

**Goal:** Detect repost/copy-paste campaigns without deleting evidence.

Build:

1. **Fingerprint generation**

    * SimHash (or MinHash)
    * store fingerprints with TTL

2. **Lookup**

    * compare against recent fingerprints by ticker/source
    * if near-dup → **KEEP**, attach tag like `NEAR_DUP_SIGNAL`

✅ **End of Phase 6**

* You preserve evidence while enabling downstream handling

---

### Phase 7 — Source-aware tuning (Reddit vs Twitter vs Telegram)

**Goal:** One pipeline, different thresholds per source.

Build:

1. **SourcePolicy config**

    * per-source thresholds:

        * min length
        * max URLs
        * emoji/caps limits
        * near-dup sensitivity

2. **Policy resolution**

    * based on `event.source`
    * default fallback policy

✅ **End of Phase 7**

* Consistent structure + source-aware behavior

---

### Phase 8 — Observability + evaluation hooks (FYP-friendly)

**Goal:** Demonstrate Service A improves quality without destroying useful patterns.

Add:

* counters per reason code (drops + tags)
* per-source metrics
* kept vs dropped %
* sampling logs for drops (small % for manual review)
* retention for `events.dropped` (7–30 days) for offline evaluation

✅ **End of Phase 8**

* You have measurable, reportable evidence for your FYP (before/after quality + drop reasons).

---

## 2) Folder structure for `filtering-service-A`

(Updated to match single usable topic + dropped audit topic)

```
filtering-service-A/
  pom.xml
  README.md

  src/main/java/com/sentrix/filtering_service_a/
    FilteringServiceAApplication.java

    config/
      KafkaConfig.java
      FilterPoliciesConfig.java
      RedisConfig.java            (optional)
      JacksonConfig.java

    messaging/
      consumer/
        EventsRawConsumer.java
      producer/
        EventsCleanedProducer.java
        EventsDroppedProducer.java
      topics/
        TopicNames.java

    model/
      event/
        KafkaEvent.java
        KafkaPostEvent.java
        KafkaCommentEvent.java
      envelope/
        FilteredEventEnvelope.java     (KafkaEvent + filter metadata)
      filter/
        HardGateDecision.java          (KEEP, DROP)
        FilterReason.java
        EventFeatures.java

    pipeline/
      FilteringPipeline.java
      PipelineContext.java

    processing/
      normalize/
        TextNormalizer.java
        UrlNormalizer.java
      extract/
        FeatureExtractor.java
      validate/
        EventValidator.java
      dedup/
        DedupService.java
        IdDeduplicator.java
        ContentHashDeduplicator.java
        FingerprintService.java
      rules/
        FilterRule.java
        RuleEngine.java
        ruleset/
          UrlSpamRule.java
          DomainDenylistRule.java
          ScamPhraseRule.java
          ExcessiveCapsRule.java
          EmojiSpamRule.java

    policy/
      SourcePolicy.java
      PolicyResolver.java

    util/
      HashingUtil.java
      TimeBucketUtil.java
      TextUtil.java
      RegexLibrary.java

  src/main/resources/
    application.yml
    policies.yml
    scam_phrases.txt
    domain_denylist.txt

  src/test/java/com/sentrix/filtering_service_a/
    ...
```

---

## 3) Responsibilities (updated)

### `EventsRawConsumer`

* reads `events.raw`
* parses message → `KafkaEvent`
* calls `FilteringPipeline.process(event)`
* if decision == KEEP → publish to `events.cleaned`
* if decision == DROP → publish to `events.dropped`

### `FilteringPipeline`

Orchestrates in order:

1. validate schema (hard drop only)
2. normalize text + extract features
3. exact dedup checks
4. apply high-precision hard-drop rules
5. compute near-dup fingerprints (keep but tag)
6. attach metadata + publish once (KEEP → cleaned / DROP → dropped)

---

## 4) Platform handling

* one unified schema (`KafkaEvent`)
* per-source thresholds via `SourcePolicy`
* optional source-specific rule toggles

# NOTE:

We keep dropped events topic for checking filtering system performance and auditing

# Create events.cleaned topic

/opt/homebrew/opt/kafka/bin/kafka-topics \
--create \
--topic sentrix.filter-service-a.cleaned \
--bootstrap-server localhost:9092 \
--partitions 3 \
--replication-factor 1 \
--config cleanup.policy=delete \
--config retention.ms=604800000

# Verify topics

/opt/homebrew/opt/kafka/bin/kafka-topics \
--describe \
--bootstrap-server localhost:9092 \
--topic sentrix.filter-service-a.cleaned

# Create events.dropped topic (audit + evaluation)

/opt/homebrew/opt/kafka/bin/kafka-topics \
--create \
--topic sentrix.filter-service-a.dropped \
--bootstrap-server localhost:9092 \
--partitions 3 \
--replication-factor 1 \
--config cleanup.policy=delete \
--config retention.ms=604800000

# Verify topics

/opt/homebrew/opt/kafka/bin/kafka-topics \
--describe \
--bootstrap-server localhost:9092 \
--topic sentrix.filter-service-a.dropped

# Commands for delete

/opt/homebrew/opt/kafka/bin/kafka-topics \
--delete \
--topic sentrix.filter-service-a.cleaned \
--bootstrap-server localhost:9092

/opt/homebrew/opt/kafka/bin/kafka-topics \
--delete \
--topic sentrix.filter-service-a.dropped \
--bootstrap-server localhost:9092

## Kafka Consumption & Failure Handling (Design Notes)

Filtering Service A uses **manual Kafka acknowledgments** to precisely control when events are considered “processed”.

### How it works

* The service **consumes events from `sentrix.ingestor.events`** with `enable-auto-commit=false`.
* Each event is processed exactly once through the **hard-gate filtering pipeline**.
* After processing:

    * **KEEP** → published to `sentrix.filter-service-a.cleaned`
    * **DROP** → published to `sentrix.filter-service-a.dropped`
* **Offsets are acknowledged only after the result is successfully published**, ensuring no silent data loss.

### Failure policy (intentional)

* **Malformed / invalid events** (e.g. JSON parse failure, missing required fields) are:

    * routed to `events.dropped`
    * **acknowledged**
    * **never retried** (poison-pill pattern)

* This prevents the consumer from getting stuck on unrecoverable messages while still preserving them for audit,
  analysis, and evaluation.

### Why this is good

* Guarantees **at-least-once processing**
* Prevents infinite retries on broken data
* Preserves dropped events for **debugging and model evaluation**
* Clean separation between:

    * **message ingestion**
    * **filtering logic**
    * **publishing & offset control**

This design matches common production Kafka patterns and keeps the pipeline reliable, observable, and FYP-friendly.

---