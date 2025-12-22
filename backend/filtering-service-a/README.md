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

### Phase 1 — Create the Spring skeleton + Kafka IO (foundation)

**Goal:** Service runs, consumes from Kafka, produces to Kafka.

Build in this order:

1. Create Spring Boot app: `filtering-service-A`

2. Add config: bootstrap, `application.yml`, env vars

3. Implement Kafka consumer that reads from `events.raw`

4. Implement Kafka producers that write to:

    * `events.cleaned`
    * `events.dropped`

5. Add structured logging + tracing:

    * log `source`, `eventId`, `KEEP/DROP`, `reasons`

✅ End of phase: pass-through works (temporary behavior is “KEEP everything” → publish to `events.cleaned`).

---

### Phase 2 — Canonicalization & feature extraction (always before rules)

**Goal:** Every kept event becomes normalized + enriched with cheap features (and dropped events still get reasons).

Build in this order:

1. Create a `Normalizer` component:

* compute `textNorm` from raw (`title` + `text`)
* standardize URLs to `<URL>`
* cashtag normalization (consistent casing/format)
* whitespace cleanup

2. Create a `FeatureExtractor`:

* extract urls/domains/mentions/cashtags/hashtags
* compute counts:

    * word count
    * url_count
    * emoji_count
    * caps_ratio
    * repeated char score

3. Update the outgoing message to carry:

* `textNorm`
* `features`
* keep original raw fields untouched

✅ End: messages published to `events.cleaned` include normalization + features.

---

### Phase 3 — Schema validation + hard failures (DROP only “definitely broken”)

**Goal:** Drop only events that are unusable, not merely suspicious.

Build:

1. Implement `Validator`:

* missing required fields → **DROP**
* empty/too-short text → usually **DROP** (config-driven threshold)
* too old (optional) → **DROP** or keep-but-tag (choose one)

2. Define reason codes:

* `MISSING_FIELD`
* `EMPTY_TEXT`
* `TOO_OLD`
* `OVERSIZE_TRUNCATED`

✅ End: Service A begins removing broken/junk events.
Dropped events are published to `events.dropped` (for audit + evaluation).

---

### Phase 4 — Exact dedup (ID + content hash)

**Goal:** Stop reprocessing duplicates and inflating downstream counts, while preserving campaign detection ability.

Build in this order:

1. Decide dedup storage:

* simplest: Redis with TTL
* fallback: in-memory LRU (dev only)

2. Implement ID dedup:

* key: `dedup:id:{source}:{eventId}`
* if seen → **DROP** with `EXACT_DUP_ID`

3. Implement content hash dedup:

* hash: `sha256(source + textNorm + ticker + time_bucket)`
* key: `dedup:hash:{hash}`
* if seen → **DROP** with `EXACT_DUP_CONTENT`

✅ End: exact duplicates removed with explainable reasons.

Note: campaign detection mainly needs **near-duplicate patterns**, not exact duplicates, so dropping exact duplicates is
typically safe.

---

### Phase 5 — Heuristic spam/scam rules (cheap wins, DROP only slam-dunks)

**Goal:** Remove only obvious spam/scams without ML, without “approving” anything.

Build:

1. Implement a rule engine pattern:

* interface like `FilterRule`
* each rule returns:

    * matched? (yes/no)
    * action: DROP or KEEP
    * reason code(s)

2. Add rules in sensible order:

* extreme URL spam rule (absurd URL count)
* denylist domains rule (high-confidence malicious domains)
* scam phrase regex rule (very high precision)
* extreme emoji / repeated chars (only if very clearly spam)
* too many tickers/cashtags (if you later support multi-ticker)

3. Thresholds must be config-driven:

* `maxUrls`, `minWords`, etc.

✅ End: obvious junk is removed, while borderline content is preserved for Service B.

---

### Phase 6 — Near-duplicate fingerprinting (KEEP but tag for downstream)

**Goal:** Detect copy-paste / repost campaigns without deleting evidence.

Build:

1. Implement fingerprint generation:

* SimHash (or MinHash)
* store fingerprint with TTL

2. Implement lookup strategy:

* compare against recent fingerprints for same ticker/source
* if near-dup → **KEEP**, but attach a tag/reason like `NEAR_DUP_SIGNAL`

✅ End: you preserve campaign signals while enabling Service B to act on them.

---

### Phase 7 — Source-aware tuning (Reddit vs Twitter vs Telegram)

**Goal:** Same pipeline, different thresholds per platform.

Build:

1. Add `SourcePolicy` config:

* per-source thresholds:

    * min text length
    * max URLs
    * emoji/caps thresholds
    * near-dup sensitivity

2. Policy resolution:

* based on `event.source`
* default policy if unknown

✅ End: consistent structure, source-aware behavior.

---

### Phase 8 — Observability + evaluation hooks (FYP-friendly)

**Goal:** Prove Service A improves data quality without destroying useful patterns.

Add:

* counters per reason code (drops + tags)
* per-source metrics
* % dropped vs kept
* optional sampling logs (small % of drops) for manual review
* retention policy for `events.dropped` (e.g., 7–30 days) for offline evaluation

✅ This makes your report much stronger.

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

/opt/homebrew/opt/kafka/bin/kafka-topics \
--describe \
--bootstrap-server localhost:9092 \
--topic sentrix.filter-service-a.dropped

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