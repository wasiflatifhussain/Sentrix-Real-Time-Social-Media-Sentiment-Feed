# Filtering Service A — Fast Filtration & Cleaning (Hard Gate)

Filtering Service A is the **first hard-gate** in the pipeline. It standardizes incoming social events, drops only
**definitely unusable** inputs + **slam-dunk structural spam**, removes ingestion-level duplicates, and annotates
near-duplicate waves for downstream analysis.

✅ **Implemented up to Phase 6** (Phase 7–8 are planned).

---

## Contract

### Input

We **reuse the ingestor `KafkaEvent` contract** (no schema fork).

Service A expects (required for KEEP):

* `eventId` **or** `dedupKey`
* `source`
* `entityType` (POST/COMMENT/etc.)
* time: at least one of `createdAtUtc` or `ingestedAtUtc`
* content: at least one meaningful text field (`text`, optionally `title`)
* `ticker` (required for ticker-based routing/dedup rules)

All other fields are optional and passed through unchanged.

### Output

Service A publishes a **filtered envelope** to two Kafka topics:

* `sentrix.filter-service-a.cleaned` — **KEEP**
* `sentrix.filter-service-a.dropped` — **DROP** (audit + evaluation)

“cleaned” means: passed hard-gate checks (schema + obvious junk), normalization/features attached. It does **not**
guarantee sentiment validity.

### Envelope metadata

For both KEEP and DROP, Service A attaches:

* `filterStage = "hard_gate_A"`
* `filterReasons[]` (non-empty for DROP; may be empty for KEEP)
* normalized text view (`textNormalized`) when available
* extracted features (counts/domains/etc.) when available

Note: for unrecoverable inputs (e.g., JSON parse failure), the envelope will contain the raw payload (or minimal
context) and reason codes, but may not contain normalization/features.

---

## Pipeline (Phases 0–6)

### Phase 0 — Lock the contract ✅ DONE

* Reuse ingestor event contract
* Two-topic output (cleaned/dropped)
* Wrap original event in an envelope with filter metadata

### Phase 1 — Spring skeleton + Kafka IO ✅ DONE

* Consume `sentrix.ingestor.events` with **manual ack**
* Publish exactly once to cleaned/dropped
* **Ack only after publish succeeds**
* Poison-pill policy: malformed/unparseable events → dropped + **ack** (no retry)

### Phase 2 — Canonicalization + feature extraction ✅ DONE

Normalization (on `title + text`):

* URLs → `<URL>`
* cashtags normalized consistently
* whitespace cleanup
* optional truncation support (`max-len`) + `wasTruncated` signal

Feature extraction:

* counts: word/url/emoji/cashtag/hashtag/mention, caps ratio, repeated char signals
* domains extracted from URLs (where applicable)

### Phase 3 — Schema validation + hard failures ✅ DONE

Drop only **definitely broken/unusable** events, config-driven:

* missing required fields
* empty/too-short normalized text
* too old (per configured max age)
* oversize handling: truncate (optionally drop if configured)

Reason codes include:

* `MISSING_FIELD`, `EMPTY_TEXT`, `TOO_OLD`, `OVERSIZE_TRUNCATED`, `RAW_PARSE_FAIL`, etc.

### Phase 4 — Exact Deduplication (ID + Content Hash) ✅ DONE

1. **Event ID dedup**

* drop duplicates by `dedupKey` (and/or stable id fallback)

2. **Content dedup (time-bucketed)**
   Drops identical `(source, normalized_text, ticker)` **only within a short ingestion-relevant window**:

```
hash(source | normalized_text | ticker | time_bucket)
time_bucket = event_epoch_seconds / bucket_seconds
```

Why buckets: catches overlap/retry/pagination artifacts without suppressing legitimate reposts across long windows.

TTL controls memory retention; buckets control dedup semantics.

### Phase 5 — Heuristic spam rules (slam-dunks only) ✅ DONE

Deterministic rules; **DROP only when extremely high-confidence**:

1. Absurd URL spam
2. Extreme emoji abuse
3. Repeated character abuse
4. Excessive cashtags / tickers

No semantic scam detection, no denylist domains, no phrase matching in Service A.

### Phase 6 — Near-duplicate fingerprinting (annotate only) ✅ DONE

Goal: detect coordinated repost/copy-paste waves without dropping.

* fingerprint: SimHash (or equivalent) over normalized text (only for sufficiently long texts)
* scope: `source + ticker + rolling window`
* compare via Hamming distance
* if match evidence crosses thresholds: KEEP + attach tag (e.g., `NEAR_DUP_WAVE`) with evidence

This phase is best-effort and approximate; it produces a **soft signal** only.

---

## Kafka Topics & Ops

### Topics used

* Input: `sentrix.ingestor.events`
* Output KEEP: `sentrix.filter-service-a.cleaned`
* Output DROP: `sentrix.filter-service-a.dropped`

### Create topics (local)

```bash
# Create events.cleaned topic
/opt/homebrew/opt/kafka/bin/kafka-topics \
--create \
--topic sentrix.filter-service-a.cleaned \
--bootstrap-server localhost:9092 \
--partitions 3 \
--replication-factor 1 \
--config cleanup.policy=delete \
--config retention.ms=604800000

# Create events.dropped topic (audit + evaluation)
/opt/homebrew/opt/kafka/bin/kafka-topics \
--create \
--topic sentrix.filter-service-a.dropped \
--bootstrap-server localhost:9092 \
--partitions 3 \
--replication-factor 1 \
--config cleanup.policy=delete \
--config retention.ms=604800000
```

### Verify topics

```bash
/opt/homebrew/opt/kafka/bin/kafka-topics \
--describe \
--bootstrap-server localhost:9092 \
--topic sentrix.filter-service-a.cleaned

/opt/homebrew/opt/kafka/bin/kafka-topics \
--describe \
--bootstrap-server localhost:9092 \
--topic sentrix.filter-service-a.dropped
```

### Delete topics

```bash
/opt/homebrew/opt/kafka/bin/kafka-topics \
--delete \
--topic sentrix.filter-service-a.cleaned \
--bootstrap-server localhost:9092

/opt/homebrew/opt/kafka/bin/kafka-topics \
--delete \
--topic sentrix.filter-service-a.dropped \
--bootstrap-server localhost:9092
```

---

## Kafka Consumption & Failure Handling (Design Notes)

Filtering Service A uses **manual Kafka acknowledgments** to control when events are considered “processed”.

* `enable-auto-commit=false`
* After processing:

    * KEEP → publish to `sentrix.filter-service-a.cleaned`
    * DROP → publish to `sentrix.filter-service-a.dropped`
* **Offsets are acknowledged only after publish succeeds**, preventing silent loss.

### Poison-pill handling (intentional)

Unrecoverable inputs (e.g., JSON parse failure / malformed messages) are:

* routed to `sentrix.filter-service-a.dropped`
* **acknowledged**
* **not retried**

This prevents the consumer from stalling on bad messages while still preserving them for audit/evaluation.

---

## Future Work (Not Implemented Yet)

### Phase 7 — Source-aware tuning (Reddit vs Twitter vs Telegram)

**Goal:** one pipeline, but thresholds vary by `event.source` (without branching logic inside rules).

Planned steps:

* Add `SourcePolicy` config with per-source overrides for:

    * `min-text-len`
    * URL/emoji/caps thresholds
    * near-dup sensitivity (`minWords`, `maxHamming`, `minMatches`, window)
* Resolve policy early in the pipeline (`policy = resolve(event.source)`), then **inject into**:

    * Phase 5 rule thresholds
    * Phase 6 near-dup parameters
* Keep a default policy fallback so unknown sources still work.

Why: same schema ≠ same distribution; prevents “tuned-for-Reddit” thresholds from harming Twitter/Telegram later.

### Phase 8 — Observability + evaluation hooks (FYP-friendly)

**Goal:** report measurable improvements without hiding mistakes.

Planned steps:

* Counters per reason code (drops + tags), plus per-source breakdown
* Keep vs drop rate + top reasons over time
* Sampled logging of dropped events (small %, safe for volume)
* Retain `sentrix.filter-service-a.dropped` for offline evaluation (7–30 days)

Why: makes the system auditable and gives you clean “before/after” evidence for the FYP write-up.
