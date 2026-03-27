# Filtering Service B — Semantic Credibility Filtering

Filtering Service B is the **second-stage smart gate** in the Sentrix pipeline. It consumes events already cleaned by Filtering Service A and applies deeper semantic and behavioral analysis to decide whether an event is credible enough to be passed into the sentiment model.

Unlike Service A, which focuses on **structural quality and obvious noise**, Service B focuses on **ticker relevance, manipulation patterns, and information value**.

Its job is not to classify sentiment. Its job is to ensure that the sentiment model only receives events that are:

* actually about the tracked ticker in a financial context
* not heavily repetitive or artificially amplified
* not low-information duplicates of recent same-ticker chatter

This design follows a **streaming, event-by-event architecture with short-term memory**, where each Kafka event is processed independently but enriched with recent ticker/account context stored in Redis.

Filtering Service B is implemented as a **single long-running Python backend microservice**. That microservice continuously consumes events from Kafka, processes them through the Filter B pipeline, reads/writes short-term contextual state in Redis, and publishes final keep/reject decisions to downstream Kafka topics. If needed, lightweight HTTP endpoints can still be exposed for health, readiness, or debugging, but the core runtime model remains a **single backend microservice**, not multiple separate services.

---

## Core Role in the Pipeline

### Upstream

Filtering Service B consumes from:

* `sentrix.filter-service-a.cleaned`

At this point, events have already passed:

* schema validation
* normalization
* exact deduplication
* heuristic hard-gate spam filtering
* near-duplicate wave tagging from Service A

So Service B does **not** redo heavy cleaning or normalization.

---

### Downstream

Filtering Service B publishes to:

* `sentrix.filter-service-b.filtered` — events accepted for sentiment analysis
* `sentrix.filter-service-b.rejected` — events rejected by semantic credibility filtering

No review lane is used in the current design.

---

## Service Runtime Model

Filtering Service B is not a passive library or a one-off batch script. It runs as a **long-lived backend microservice**.

That single microservice is responsible for:

* subscribing to the cleaned-event Kafka topic
* polling Kafka continuously for new events
* processing each event through the Filter B pipeline
* reading recent ticker/account state from Redis
* updating Redis after processing
* publishing the final decision to downstream Kafka topics
* acknowledging offsets only after successful publish
* optionally exposing lightweight HTTP endpoints for health, readiness, or debugging

So the correct mental model is:

> **one Python backend microservice continuously listening to Kafka, running the semantic credibility pipeline, and forwarding results downstream**

If FastAPI is used, it is simply the HTTP/service shell around that same microservice. It is **not** a separate backend and it is **not** the thing replacing Kafka consumption. The Kafka event loop remains part of the same service.

---

## Design Philosophy

Service B is designed around **one final running credibility score**, rather than many independent final scores.

Internally, different signals are computed during the pipeline, but those signals are only used to:

* penalize the running credibility score
* occasionally provide a small boost
* trigger rare high-confidence rejections in extreme cases

This keeps the system:

* easier to reason about
* easier to tune
* easier to explain in the FYP
* less fragmented than exposing many independent model outputs

The final output of the service is therefore centered around:

* `credibilityScore`
* `decision` (`KEEP` or `REJECT`)
* `decisionReasons[]`

---

## High-Level Processing Model

Although Kafka delivers one event at a time, Service B does **not** make decisions in complete isolation.

Each incoming event is processed using:

1. the current event itself
2. recent same-ticker context
3. recent same-author same-ticker context
4. recent similarity history and burst counters

This means Service B is best understood as:

> **a streaming event processor with short-term ticker-scoped memory**

Kafka provides the event stream. Redis provides the recent state needed for stateful checks.

---

## Technology Choice

### Recommended stack

**Language:** Python

**Reasoning:**

* strong support for NLP and embedding workflows
* easier experimentation with thresholds and scoring
* good fit for sentence-transformers and future model evolution
* easier offline evaluation and later classifier training

### Supporting technologies

* **Kafka** for event consumption and output publishing
* **Redis** for short-term contextual state
* **sentence-transformers** for semantic similarity
* **Pydantic** for schemas and validation
* **FastAPI** (optional) for health/readiness/debug/admin endpoints if you want the service to expose HTTP routes
* **scikit-learn** (later phase) for possible logistic regression upgrade

### Runtime note

FastAPI is optional and should be viewed only as a convenience/service shell. The important part is that Filter B remains **one backend microservice** whose main job is Kafka-driven event processing.

---

## Responsibilities of Service B

Filtering Service B is responsible for:

* checking whether a cleaned event is genuinely about the tracked ticker in a financial/investing context
* detecting suspicious repeated messaging across different accounts
* detecting repetitive same-account ticker pushing
* measuring whether an event adds meaningful new information relative to recent accepted ticker events
* maintaining a single running credibility score across stages
* deciding whether to keep or reject the event for downstream sentiment analysis

It is **not** responsible for:

* structural data cleaning
* exact deduplication
* obvious hard spam filtering
* sentiment classification
* long-term storage of all historical events

Those responsibilities belong elsewhere in the broader Sentrix system.

---

## Final Pipeline Layout

Service B is intentionally kept to **three main stages** plus final routing.

---

# Stage 1 — Ticker Relevance

## Goal

Determine whether the event is **actually about the tracked ticker/company/stock in a financial context**, rather than merely containing the ticker string.

This is especially important for:

* ambiguous ticker symbols
* casual mentions
* unrelated chatter
* posts that mention a ticker without discussing the company or stock meaningfully

---

## Why this stage comes first

Ticker relevance is the most fundamental semantic filter in Service B.

If an event is not really about the ticker, then running more advanced behavioral and novelty checks on it is not worthwhile.

This stage therefore acts as the earliest semantic gate.

---

## Method

The recommended first implementation uses **sentence-transformer embeddings**, not a separate trained classifier.

### Why embeddings are preferred initially

* they are reusable across multiple stages
* they do not require labeled classifier training upfront
* they work well for semantic similarity
* the same embedding model can later be reused for novelty and semantic comparison

---

## Inputs

For each event, use:

* cleaned normalized text from Service A
* optional title if present
* ticker symbol
* prebuilt ticker/company reference text

The semantic text used for embedding can be:

* `title + text`, if title exists
* otherwise just `text`

---

## Relevance strategy

Compute semantic similarity between:

* the event text embedding
* a precomputed ticker/company profile embedding

The ticker/company profile may contain compact reference text such as:

* company name
* ticker symbol
* sector/business summary
* common finance-related context words

For example, a ticker profile might encode something like:

* company identity
* stock/investment context
* earnings/business terminology associated with the company

This helps reduce false positives from ambiguous ticker mentions.

---

## Decision behavior

This stage primarily affects the running credibility score.

### Recommended behavior

* **strong relevance** → no penalty, optional slight boost
* **moderate relevance** → mild penalty
* **weak relevance** → strong penalty
* **extremely low relevance** → immediate reject

Immediate rejection should only happen in the strongest low-relevance cases.

This prevents obviously irrelevant events from progressing further through the pipeline.

---

## Output of this stage

Internal signal only:

* relevance contribution to final credibility score
* optional reason tag:

  * `LOW_TICKER_RELEVANCE`

No separate externally visible complex scoring is required.

---

# Stage 2 — Manipulation / Repetition Analysis

## Goal

Detect whether the event looks like part of:

* coordinated repeated messaging
* multi-account copy-paste behavior
* repeated same-account ticker pushing
* suspicious amplified chatter around the ticker

This is the main behavioral credibility stage.

---

## Why these checks are grouped together

Several suspicious behaviors overlap in purpose:

* cross-user repeated messaging
* cluster density
* same-account repetitive posting
* burst-amplified repetition

All of them are trying to answer a common question:

> “Does this event look artificially amplified, coordinated, or low-credibility due to repetition behavior?”

So rather than turning each into its own full pipeline stage, they are grouped together under one broader **manipulation/repetition stage**.

---

## 2A — Cross-User Repeated Messaging

### Goal

Detect when very similar content is being repeated by different users around the same ticker within a recent time window.

This helps catch:

* copy-paste promotional campaigns
* coordinated message pushing
* spam-style repeated financial narratives

---

### Method

Use:

* **SimHash**
* Hamming distance
* recent same-ticker event state from Redis

For each new event:

1. compute a SimHash from normalized text
2. fetch recent same-ticker candidate fingerprints
3. compare by Hamming distance
4. identify sufficiently similar prior events

---

### Effect on scoring

* isolated match or weak evidence → small or no penalty
* repeated similar posts across multiple authors → stronger penalty

This signal should usually **penalize**, not directly reject, unless evidence is extreme.

---

## 2B — Cluster Density Signal

### Goal

Measure how concentrated the event’s similarity neighborhood is.

This is not a separate stage. It is an extension of cross-user repeated messaging.

Instead of only asking:

* “did I match one similar event?”

the system also asks:

* “is this event sitting inside a dense cluster of similar same-ticker posts?”

---

### Why cluster density matters

A single duplicate may be weak evidence.

But many highly similar posts:

* within a short time
* for the same ticker
* from multiple different authors

is much stronger evidence of suspicious amplification.

---

### Method

After finding similar events in the recent same-ticker window, compute simple density measures such as:

* `matchCount`
* `uniqueAuthorCount`
* `timeSpanSeconds`
* optional average Hamming closeness

A denser cluster leads to a larger penalty.

---

### Integration

Cluster density is integrated directly into the Stage 2 penalty logic.

It does not need its own published score or output topic.

---

## 2C — Same-Account Repetitive Pushing

### Goal

Detect when a single account repeatedly pushes the same ticker with near-duplicate content over short periods.

This captures a different pattern from cross-user coordination.

Cross-user repetition asks:

* are many users repeating similar content?

Same-account repetition asks:

* is one user repeatedly pushing the same narrative?

---

### Method

Use recent author+ticker history in Redis.

For each new event:

1. fetch recent same-author same-ticker events
2. compare current event to that history
3. measure near-duplicate behavior and short-interval repetition

---

### Effect on scoring

* mild repeated behavior → moderate penalty
* strong same-account repetitive pushing → strong penalty
* extreme repeated same-account pumping → optional immediate reject

This is one of the rare cases where a direct reject may be justified.

---

## 2D — Burst Context

### Goal

Capture whether the ticker is currently experiencing an abnormal local spike in message activity.

Burst should **not** be used as a standalone rejection rule.

Real market news can naturally cause genuine bursts.

Instead, burst should act as a **supporting amplifier**.

---

### Method

Maintain recent ticker counts and compare current activity against a short rolling baseline.

Possible measures:

* recent message count in short window
* baseline count from earlier windows
* simple burst ratio

---

### Role in scoring

Burst alone should not drive rejection.

But if:

* burst is high
* cluster density is high
* repeated messaging is high

then the manipulation penalty should be increased.

Burst therefore acts as a contextual multiplier inside Stage 2.

---

## Stage 2 Outcome

This stage applies penalties to the running credibility score using:

* cross-user repeated messaging
* cluster density
* same-account repetitive pushing
* burst amplification

Possible reason tags include:

* `CROSS_USER_REPETITION`
* `DENSE_SIMILARITY_CLUSTER`
* `SAME_ACCOUNT_REPETITION`
* `BURST_AMPLIFIED_REPETITION`

Only one or two of these may be attached as needed; reasons should remain concise.

---

# Stage 3 — Novelty / Information Value

## Goal

Determine whether the event adds meaningful new information, or whether it is largely redundant relative to recent accepted events for the same ticker.

This stage filters out low-information repeated chatter that may not be obvious spam but still reduces sentiment signal quality.

---

## Why this stage is separate from Stage 2

Stage 2 focuses on **manipulation behavior**.

Stage 3 focuses on **information value**.

An event may be:

* not obviously coordinated
* not from a spammy author
* still quite low-value because it adds nothing new

This stage catches that.

---

## Method

Use sentence-transformer embeddings again.

Compare the current event embedding against **recent accepted same-ticker events**, not all recent raw events.

This is important.

If novelty is measured against all incoming events, then noisy events can poison the reference set.

By comparing mainly against accepted events, novelty is anchored to cleaner recent ticker memory.

---

## Decision behavior

* highly redundant / very low novelty → penalty
* moderate novelty → no strong change
* clearly distinct / new information → no penalty, optional slight boost

Novelty should **not** usually act as a hard reject on its own.

It is best used as a final refinement penalty.

---

## Output of this stage

This stage affects only the running credibility score and optional decision reasons such as:

* `LOW_NOVELTY`

No separate output lane is required.

---

# Final Decision Layer

After all three stages, Service B computes the final decision.

---

## Running score strategy

The system begins with a base credibility score, for example:

* `credibilityScore = 1.0`

Then each stage:

* subtracts penalties
* optionally adds a small boost
* may trigger immediate rejection in rare extreme cases

This approach is preferred over many separate exposed scores because it is:

* cleaner
* more explainable
* easier to debug
* easier to tune experimentally

---

## Final routing

At the end of processing:

* if score is above threshold → `KEEP`
* otherwise → `REJECT`

The service then publishes to the appropriate Kafka topic.

---

## Output envelope

Each output event should include:

* original cleaned event
* `filterStage = "semantic_gate_B"`
* `credibilityScore`
* `decision`
* `decisionReasons[]`

This keeps the service auditable while staying compact.

---

## No review lane

There is intentionally no review topic in the current design.

This keeps the pipeline operationally simpler and avoids introducing an extra ambiguous class.

Only two final decisions are used:

* keep
* reject

---

## Redis Usage

Redis is essential because several Service B checks require recent context, not just the current event.

Service B does **not** fetch the entire ticker history on every event.

Instead, it keeps **short-term rolling state**.

This is more scalable and more appropriate for streaming systems.

---

# Redis State Design

## 1. Recent same-ticker similarity state

Used for:

* cross-user repeated messaging
* cluster density

Store recent entries keyed by ticker, possibly also source+ticker if needed.

Each entry may include:

* event id
* author id
* timestamp
* SimHash
* optional lightweight metadata

TTL should reflect the active suspicious window, such as minutes to hours.

---

## 2. Recent same-author same-ticker state

Used for:

* same-account repetitive pushing

Store recent entries keyed by:

* `author + ticker`

Each entry may include:

* event id
* timestamp
* SimHash

TTL can be somewhat longer than the cluster window.

---

## 3. Recent accepted same-ticker semantic state

Used for:

* novelty / information value

Store only recent accepted events for each ticker.

Each entry may include:

* event id
* timestamp
* embedding vector or reference to embedding cache

This state should be updated primarily for kept events, not all incoming events.

---

## 4. Ticker burst counters

Used for:

* burst context

Store time-bucketed counts per ticker, such as per-minute or short-window counts.

This allows comparison between:

* immediate recent volume
* short rolling baseline

---

# State Update Rules

State should be updated carefully.

Not every Redis structure should be populated in the same way.

---

## Raw similarity state

Can include most incoming events, because repetition evidence is useful even for suspicious events.

---

## Accepted semantic novelty state

Should mostly include only kept events.

This prevents novelty memory from being polluted by rejected spammy chatter.

---

## Burst counters

Should generally count incoming same-ticker traffic regardless of final decision, since they represent activity context.

---

# Kafka Topics

## Input

* `sentrix.filter-service-a.cleaned`

## Output

* `sentrix.filter-service-b.filtered`
* `sentrix.filter-service-b.rejected`

---

## Local topic creation example

```bash
# Create filtered topic
/opt/homebrew/opt/kafka/bin/kafka-topics \
--create \
--topic sentrix.filter-service-b.filtered \
--bootstrap-server localhost:9092 \
--partitions 3 \
--replication-factor 1 \
--config cleanup.policy=delete \
--config retention.ms=604800000

# Create rejected topic
/opt/homebrew/opt/kafka/bin/kafka-topics \
--create \
--topic sentrix.filter-service-b.rejected \
--bootstrap-server localhost:9092 \
--partitions 3 \
--replication-factor 1 \
--config cleanup.policy=delete \
--config retention.ms=604800000
```

---

# Development Layout / Suggested Project Structure

A possible initial Python structure:

```text
filter-service-b/
├── README.md
├── requirements.txt
├── app/
│   ├── main.py
│   ├── config.py
│   ├── consumer/
│   │   └── kafka_consumer.py
│   ├── producer/
│   │   └── kafka_producer.py
│   ├── models/
│   │   ├── event.py
│   │   ├── envelope.py
│   │   └── scoring.py
│   ├── pipeline/
│   │   ├── processor.py
│   │   ├── relevance_stage.py
│   │   ├── manipulation_stage.py
│   │   ├── novelty_stage.py
│   │   └── final_decision.py
│   ├── similarity/
│   │   ├── simhash_utils.py
│   │   ├── embedding_service.py
│   │   └── cluster_utils.py
│   ├── state/
│   │   ├── redis_client.py
│   │   ├── ticker_state_store.py
│   │   ├── author_state_store.py
│   │   └── burst_store.py
│   ├── profiles/
│   │   └── ticker_profiles.py
│   └── api/
│       └── debug_routes.py   # optional
└── tests/
    ├── unit/
    └── integration/
```

This keeps the code aligned with the actual pipeline stages.

If you want to expose health/readiness/debug endpoints, you can still use FastAPI inside this same microservice. That would remain part of the same backend service rather than becoming a separate architectural component.

---

# End-to-End Processing Flow

For each incoming cleaned event:

1. start the Filter B microservice
2. connect to Kafka and Redis
3. subscribe to `sentrix.filter-service-a.cleaned`
4. poll Kafka for the next event
5. read current event fields from Service A output
6. fetch necessary Redis context
7. initialize running credibility score
8. run Stage 1 ticker relevance
9. if not immediately rejected, run Stage 2 manipulation/repetition analysis
10. run Stage 3 novelty/information value analysis
11. apply final threshold
12. publish result to filtered or rejected topic
13. update Redis state stores appropriately
14. acknowledge Kafka offset only after publish succeeds

---

# Failure Handling

Filtering Service B should follow the same reliable processing philosophy as Service A.

---

## Consumer behavior

* consume with manual acknowledgment
* only acknowledge after output publish succeeds

This prevents silent loss.

---

## Malformed input handling

If Service B receives malformed or unusable input despite upstream guarantees:

* route to rejected topic if possible
* include reason such as `INVALID_INPUT`
* acknowledge after reject publish succeeds

Poison-pill behavior should remain operationally safe.

---

# Development Roadmap

The service should be built incrementally in phases.

This keeps the implementation realistic and testable.

---

## Phase 0 — Contract and Scope Lock

### Goal

Lock the service contract and prevent scope drift.

### Deliverables

* confirm input topic
* confirm output topics
* define output envelope fields
* define running-score philosophy
* confirm no review lane
* define initial reason-code vocabulary

### Why this phase matters

This prevents later redesign caused by unclear output expectations.

---

## Phase 1 — Service Skeleton + Kafka IO

### Goal

Build the basic working consumer/producer pipeline.

### Deliverables

* Python project skeleton
* Kafka consumer wired to `sentrix.filter-service-a.cleaned`
* Kafka producer for filtered/rejected outputs
* manual ack flow
* basic envelope creation
* configuration loading
* simple debug logging
* optional FastAPI health/debug endpoints if desired

### Exit condition

Service can consume one cleaned event and publish a keep/reject decision.

---

## Phase 2 — Redis State Layer

### Goal

Introduce the stateful context infrastructure required for advanced checks.

### Deliverables

* Redis client setup
* ticker-level similarity state storage
* author+ticker history storage
* novelty memory for accepted events
* burst counters
* TTL policies for each state type

### Exit condition

Service can store and retrieve recent ticker/account context successfully.

---

## Phase 3 — Stage 1 Ticker Relevance

### Goal

Implement the first semantic gate.

### Deliverables

* sentence-transformer integration
* ticker/company profile definitions
* relevance scoring logic
* relevance penalty rules
* extreme low-relevance reject logic
* unit tests for ambiguous / relevant / irrelevant cases

### Exit condition

Service can reliably penalize or reject low-relevance ticker mentions.

---

## Phase 4 — Stage 2 Manipulation / Repetition

### Goal

Implement behavioral credibility filtering.

### Deliverables

* SimHash generation
* Hamming similarity comparison
* recent same-ticker candidate search
* cross-user repeated messaging penalty
* cluster density penalty
* same-account repetitive posting penalty
* burst-based amplification logic

### Exit condition

Service can detect suspicious repetitive patterns and apply score penalties.

---

## Phase 5 — Stage 3 Novelty / Information Value

### Goal

Add final redundancy filtering for low-information chatter.

### Deliverables

* embedding reuse for novelty comparison
* recent accepted same-ticker reference retrieval
* novelty penalty logic
* optional slight boost for clearly distinct content

### Exit condition

Service can downrank redundant chatter even when not obviously spammy.

---

## Phase 6 — Final Scoring and Routing

### Goal

Finalize one coherent scoring path.

### Deliverables

* central scoring object
* final keep/reject threshold
* decision reason collection
* consistent output envelope
* publish routing logic

### Exit condition

Service can fully process events end-to-end with stage-based scoring.

---

## Phase 7 — Evaluation and Threshold Tuning

### Goal

Tune the system with real examples.

### Deliverables

* sample dataset of kept and rejected outputs
* manual review of borderline cases
* threshold adjustments
* reason-code frequency checks
* false-positive / false-negative notes

### Why this phase matters

The score design will only become useful after tuning against real pipeline behavior.

---

## Phase 8 — Observability and FYP Metrics

### Goal

Make the service measurable and explainable.

### Deliverables

* counts by reason code
* keep vs reject rate
* per-stage penalty contribution logging
* source-wise outcome breakdown
* sampled rejected-event logs for offline analysis

### Why this phase matters

This provides strong material for evaluation, reporting, and demo discussion.

---

## Phase 9 — Optional Model Upgrade

### Goal

Improve final decisioning once labeled data exists.

### Optional future upgrade

Replace or augment fixed weighted scoring with:

* logistic regression using internal stage signals as features

Possible features:

* relevance contribution
* cross-user repetition evidence
* cluster density evidence
* same-account repetition evidence
* burst amplification evidence
* novelty penalty

### Why this is optional

Weighted scoring is better for the initial implementation because it is simpler and more transparent.

Classifier-based final decisioning should come only after enough labeled data has been collected.

---

# Suggested Order of Actual Development

If implementing practically, the best order is:

1. Phase 0 — contract lock
2. Phase 1 — Kafka skeleton
3. Phase 2 — Redis state layer
4. Phase 3 — ticker relevance
5. Phase 4 — manipulation/repetition
6. Phase 6 — final score wiring
7. Phase 5 — novelty
8. Phase 7 — threshold tuning
9. Phase 8 — observability
10. Phase 9 — optional classifier upgrade

Reason:

* relevance and repetition are more foundational
* final scoring should exist before novelty becomes useful
* novelty works best once keep-path state already exists

---

# Initial Minimum Viable Version

A realistic MVP of Service B would include only:

* Kafka input/output
* Redis state
* Stage 1 ticker relevance
* Stage 2 cross-user repetition + same-account repetition
* final keep/reject score

Then add:

* cluster density
* burst amplifier
* novelty
* optional FastAPI endpoints

This gives you a fast usable version before full refinement.

---

# Final Summary

Filtering Service B is the **semantic credibility gate** of Sentrix.

It processes already-cleaned events from Filtering Service A and decides whether they are worth passing into the sentiment model by evaluating:

* ticker relevance
* manipulation/repetition behavior
* information novelty

---

## Temporary Note — Phase 4 Step 2 Thresholds (Cross-User Repetition)

Current implementation values in `filtering-service-b`:

* `MANIPULATION_CROSS_USER_ENABLED=true`
  Justification: keep Stage 2 signal active by default so repeated-copy behavior is not missed.
* `MANIPULATION_CROSS_USER_MAX_HAMMING=5`
  Justification: aligns with SimHash near-dup sensitivity used in Service A (strict near-duplicate neighborhood on 64-bit SimHash).
* `MANIPULATION_CROSS_USER_MIN_MATCHES=2`
  Justification: one similar post can be incidental; two or more similar matches is stronger evidence.
* `MANIPULATION_CROSS_USER_MIN_UNIQUE_AUTHORS=2`
  Justification: requires multi-account evidence, avoids treating single-user repetition as cross-user coordination.
* `MANIPULATION_CROSS_USER_PENALTY=0.20`
  Justification: meaningful but not overwhelming penalty; keeps Stage 1 relevance dominant unless repetition evidence is strong.
* `MANIPULATION_CROSS_USER_STRONG_MATCHES=4`
  Justification: higher bar for escalated action to reduce false positives.
* `MANIPULATION_CROSS_USER_STRONG_PENALTY=0.35`
  Justification: stronger downrank for dense repeated messaging across accounts.

Behavior summary:

* Penalty applies only when both conditions are true:
  * `matchCount >= MANIPULATION_CROSS_USER_MIN_MATCHES`
  * `uniqueAuthorCount >= MANIPULATION_CROSS_USER_MIN_UNIQUE_AUTHORS`
* Candidate similarity condition is:
  * `hammingDistance(currentSimHash, candidateSimHash) <= MANIPULATION_CROSS_USER_MAX_HAMMING`
* Strong penalty applies when:
  * `matchCount >= MANIPULATION_CROSS_USER_STRONG_MATCHES`

Temporary implementation note:

* Stage 2 repetition/cluster checks are evaluated per incoming event.
* Penalties are applied only to the current event being processed.
* Historical neighbor events are used as evidence from Redis state and are not retroactively re-scored or re-routed.

The service is built as a **streaming event processor with short-term Redis-backed memory**, and it uses a **single running credibility score** rather than many fragmented final outputs.

The development plan is intentionally phased so that the system can be implemented, tested, and tuned incrementally without overcomplicating the first working version.

```bash
poetry install  # if not installed or something new added
uvicorn filtering_service_b.main:app --host 0.0.0.0 --port 8012 --app-dir src
```


```bash
cd backend/filtering-service-b
poetry lock
poetry install --extras dev
poetry run pytest -q tests/unit
```
