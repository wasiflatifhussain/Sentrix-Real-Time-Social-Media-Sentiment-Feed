# Filtration & Cleaning Pipeline Design

To progressively remove low-quality, irrelevant, and spam-like events while preserving recall, the filtration stage is
split into **two microservices**: a fast rule-based *Hard Gate* and a deeper ML/NLP-based *Soft Gate*.

---

## Service A: Fast Filtration & Cleaning (Hard Gate)

**Goal:**
Efficiently remove *clearly invalid, duplicate, or low-quality events* and standardize remaining data so that downstream
ML/NLP processing is reliable and cost-effective.
This service does **not** attempt semantic relevance or final spam decisions.

**Best stack:** **Java / Spring Boot**
(chosen for Kafka integration, throughput, type safety, and operational consistency with the ingestor)

---

### A1) Canonicalization & normalization

These steps improve **deduplication**, **heuristic filtering**, and **downstream model quality**.

* Create a normalized text representation `text_norm`:

    * lowercase
    * normalize whitespace
    * replace URLs with placeholder (`<URL>`)
    * strip tracking parameters
    * normalize cashtags (`$tsla` → `$TSLA`)
    * Unicode normalization (NFKC) and removal of zero-width characters

* Extract and store lightweight features:

    * `urls[]` and domain list
    * `mentions[]`, hashtags, cashtags
    * `num_chars`, `num_words`
    * `url_count`, `emoji_count`
    * `caps_ratio`

* Preserve original content:

    * keep `text_raw` untouched for auditing, debugging, and traceability

---

### A2) Schema validation & routing rules

* Drop events with missing essential fields:

    * `source`, `event_time`, `text_raw`
* Drop or route events that are too old (late arrivals)
* Enforce maximum payload size:

    * truncate overly long text safely while retaining raw content if required

---

### A3) Exact deduplication (cheap and deterministic)

This layer complements preliminary deduplication done during ingestion.

* ID-based deduplication (when available):

    * Twitter/X: tweet ID / retweet handling
    * Telegram: `(channel_id, message_id)`
    * Reddit: fullname ID (post/comment)

* Content-based deduplication:

    * compute `sha256(source + text_norm + ticker_set + time_bucket)`

* Maintain a rolling dedup store:

    * Redis with TTL (7–30 days), or
    * Kafka Streams / RocksDB state store

Exact duplicates are high-confidence noise and may be dropped immediately.

---

### A4) Near-duplicate & repost detection (still lightweight)

Designed to catch repost farms and copy-paste campaigns, especially common on Telegram and Twitter.

* Generate similarity fingerprints (e.g., **SimHash** or **MinHash**) from `text_norm`
* Compare against recent fingerprints within a sliding time window
* If similarity exceeds a threshold:

    * **do not immediately drop**
    * route to `events.suspect` for downstream evaluation

This avoids aggressive false positives while reducing duplicate signal inflation.

---

### A5) Obvious spam and scam heuristics

Rule-based heuristics catch a large fraction of spam at very low cost.

* URL and domain signals:

    * excessive number of URLs
    * suspicious TLDs or URL shorteners
    * configurable domain allow/deny lists

* Textual pattern signals:

    * known scam phrases (“guaranteed profit”, “signal group”, “DM me”, “VIP”, “airdrop”)
    * excessive repeated characters (`!!!!`, `$$$$`)
    * extreme emoji density

* Metadata-based signals (if available from ingestor):

    * identical content posted across many tickers or channels
    * forwarded-message patterns (Telegram)
    * abnormal posting frequency

All rules are **config-driven**, not hardcoded, to allow tuning without redeployment.

---

### A6) Basic ticker sanity checks (non-semantic)

These checks ensure structural plausibility before expensive relevance modeling.

* Route to suspect if:

    * no tickers extracted
    * unusually large ticker list (e.g., spam templates listing many tickers)
* Optional source-specific constraints:

    * e.g., Twitter events may be expected to contain cashtags

These checks **do not determine semantic relevance** — they only flag potentially noisy inputs.

---

### Outputs (Kafka topics)

Service A is intentionally conservative and recall-oriented.

It produces:

* `events.cleaned`
  Events that pass hygiene, normalization, and basic filtering
  *(safe to spend downstream compute on)*

* `events.suspect`
  Events with ambiguous or borderline signals requiring ML/NLP judgment

* `events.dropped` (optional)
  High-confidence garbage (invalid schema, exact duplicates, extreme spam)

Each output event includes:

* `filter_stage = "hard"`
* `filter_reasons[]`
  (e.g., `EXACT_DUP`, `URL_SPAM`, `NEAR_DUP`, `TOO_MANY_TICKERS`)

---

## Service B: Deep Relevance + Bot/Spam Scoring (Soft Gate)

**Goal:**
Determine **semantic relevance to the target ticker** and assign **probabilistic bot/spam scores** using NLP/ML methods.

**Best stack:** **Python**
(selected for rapid experimentation and NLP ecosystem support)

This service consumes:

* `events.cleaned`
* `events.suspect`

---

### B1) Language identification & translation strategy

* Perform language detection on incoming events
* Translation is applied **only if**:

    * the text is non-English
    * the sentiment model expects English
    * the language is not natively supported

Store:

* `lang`
* `text_en` (only if translation is applied)
* retain original text for traceability

---

### B2) Semantic ticker relevance modeling

This stage answers: *“Is this event actually about the ticker?”*

Approaches (in increasing sophistication):

1. **Contextual keyword disambiguation**

    * handle ambiguous tickers (e.g., CAT, IT, ALL)
    * require nearby finance-related context

2. **Embedding similarity (recommended)**

    * encode text with a lightweight embedding model
    * compare against a ticker profile embedding
    * threshold similarity score

3. **Lightweight classifier**

    * binary relevant/irrelevant classifier trained on labeled samples

Outputs:

* `relevance_score` ∈ [0, 1]
* `relevance_decision` (keep / reject / review)

---

### B3) Bot and spam probability scoring

Instead of binary rules, assign probabilistic scores:

* repetition similarity to spam clusters
* domain reputation features
* message template similarity
* user/channel reputation and posting behavior

Outputs:

* `spam_score` ∈ [0, 1]
* `bot_score` ∈ [0, 1] (optional)

---

### B4) Cross-source clustering (optional)

* cluster semantically similar events across Reddit, Twitter, Telegram
* detect coordinated campaigns
* cluster-level spam labeling

This is optional but provides strong analytical value if implemented.

---

### Outputs (Kafka topics)

* `events.filtered`
  Final high-quality events used by the sentiment analysis model

* `events.rejected`
  Rejected events with scores and reasons

* `events.review` (optional)
  Borderline cases retained for analysis or evaluation

---

## Final division of responsibilities

### Java / Hard Gate

* normalization & canonical fields
* exact and near-duplicate detection
* rule-based spam/scam heuristics
* basic ticker sanity checks
* routing and explainable logging

### Python / Soft Gate

* language detection & translation
* semantic relevance modeling
* probabilistic bot/spam scoring
* optional cross-source clustering

This design follows an **industry-style fast-gate / smart-gate pipeline**, balancing throughput, cost, and accuracy.
