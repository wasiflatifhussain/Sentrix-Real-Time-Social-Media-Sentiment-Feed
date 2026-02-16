# Sentrix — Local Development Setup Guide

This guide explains how to set up **Sentrix locally from scratch** on a machine with **no existing tooling installed**.

Target audience: new contributors / first-time setup.

---

## 0. System Assumptions

Supported:

- macOS (Intel / Apple Silicon)
- Linux (Ubuntu preferred)

Windows users should use WSL2 (not covered here).

---

## 1. Global Tools (Install Once)

### 1.1 Git

Check if Git exists:

```bash
git --version
```

If missing (macOS):

```bash
xcode-select --install
```

---

### 1.2 Java (for Spring Boot services)

Sentrix Java services require **Java 17**.

Install using Homebrew:

```bash
brew install openjdk@17
```

Add to shell config (`~/.zshrc`):

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@17
export PATH="$JAVA_HOME/bin:$PATH"
```

Verify:

```bash
java -version
```

---

### 1.3 IntelliJ IDEA (Recommended)

Install **IntelliJ IDEA Community Edition**
[https://www.jetbrains.com/idea/download/](https://www.jetbrains.com/idea/download/)

Used for:

- ingestor-service
- filter-service-a

---

### 1.4 Python (for FastAPI services)

Python **3.10+** required.

```bash
python3 --version
```

If missing:

```bash
brew install python
```

---

### 1.5 Node.js (for frontend)

```bash
node -v
npm -v
```

If missing:

```bash
brew install node
```

---

## 2. Kafka (Local Infrastructure)

Kafka is required for **all inter-service communication**.

### 2.1 Start Kafka (Homebrew Services)

Run the following **from your local terminal**:

```bash
brew services start kafka
```

Verify Kafka is running:

```bash
brew services list | grep kafka
```

To stop Kafka:

```bash
brew services stop kafka
```

Kafka runs on:

```
localhost:9092
```

---

## 3. Kafka Topic Setup (Exact Commands Used in This Project)

Kafka binaries are located at:

```
/opt/homebrew/opt/kafka/bin
```

All Kafka commands below **must be run from your local terminal**.

---

### 3.1 Create Topics

#### Ingestor topic

```bash
/opt/homebrew/opt/kafka/bin/kafka-topics \
  --create \
  --topic sentrix.ingestor.events \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1
```

#### Filter Service A topics

```bash
/opt/homebrew/opt/kafka/bin/kafka-topics \
  --create \
  --topic sentrix.filter-service-a.cleaned \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1
```

```bash
/opt/homebrew/opt/kafka/bin/kafka-topics \
  --create \
  --topic sentrix.filter-service-a.dropped \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1
```

---

### 3.2 Verify Topics Were Created

```bash
/opt/homebrew/opt/kafka/bin/kafka-topics \
  --describe \
  --topic sentrix.ingestor.events \
  --bootstrap-server localhost:9092
```

Repeat for other topics as needed.

---

### 3.3 Set Retention Policy (EXACTLY 7 DAYS)

Kafka retention is configured **after topic creation**.

**7 days = 604800000 ms**

Apply retention:

```bash
/opt/homebrew/opt/kafka/bin/kafka-configs \
  --bootstrap-server localhost:9092 \
  --alter \
  --entity-type topics \
  --entity-name sentrix.ingestor.events \
  --add-config retention.ms=604800000
```

Repeat for Filter Service A topics:

```bash
/opt/homebrew/opt/kafka/bin/kafka-configs \
  --bootstrap-server localhost:9092 \
  --alter \
  --entity-type topics \
  --entity-name sentrix.filter-service-a.cleaned \
  --add-config retention.ms=604800000
```

```bash
/opt/homebrew/opt/kafka/bin/kafka-configs \
  --bootstrap-server localhost:9092 \
  --alter \
  --entity-type topics \
  --entity-name sentrix.filter-service-a.dropped \
  --add-config retention.ms=604800000
```

---

### 3.4 Verify Retention (7 Days)

```bash
/opt/homebrew/opt/kafka/bin/kafka-configs \
  --bootstrap-server localhost:9092 \
  --describe \
  --entity-type topics \
  --entity-name sentrix.ingestor.events
```

Expected:

```
retention.ms=604800000
```

---

## 4. Kafka UI (Kafdrop)

Kafdrop allows inspection of topics, partitions, and messages.

Install:

```bash
brew install kafdrop
```

Run (from local terminal):

```bash
kafdrop \
  --kafka.brokerConnect=localhost:9092 \
  --server.port=9000
```

Open:

```
http://localhost:9000
```

---

## 5. Ingestor Service (Spring Boot)

### 5.1 Requirements

- Java 17
- Kafka running
- Kafka topics created
- Reddit API credentials

---

### 5.2 Environment Variables (IntelliJ Run Config)

In **IntelliJ**:

1. Open `backend/ingestor-service`
2. Go to **Run → Edit Configurations**
3. Under **Environment Variables**, add:

```
CLIENT_ID=xxxx;
CLIENT_SECRET=xxxx;
REDDIT_USERNAME=xxxx;
REDDIT_PASSWORD=xxxx
```

These must be set **inside IntelliJ**, not via terminal export.

---

### 5.3 Run Ingestor

Run:

```
IngestorServiceApplication
```

Service runs on:

```
http://localhost:8080
```

---

### 5.4 Trigger Ingestion (Manual)

From **local terminal**:

```bash
curl -X POST http://localhost:8080/debug/reddit/run
```

Notes:

- This request can take a long time (many Reddit queries).
- Watch the **IntelliJ application logs** for progress.
- Kafka publish logs confirm successful ingestion.

---

### 5.5 Verify Ingestor Output

In **Kafdrop**, check:

```
sentrix.ingestor.events
```

Messages should appear once ingestion runs.

---

## 6. Filtering Service A (Spring Boot)

### 6.1 Requirements

- Java 17
- Kafka running
- Topics created

---

### 6.2 Redis Note (Important)

Filtering Service A is designed to support Redis in the future, but:

- Redis is **NOT required** for the current implementation
- No Redis installation or configuration is needed to run this service locally

---

### 6.3 Run Filter Service A

In IntelliJ:

- Open `backend/filter-service-a`
- Run:

```
FilterServiceAApplication
```

---

### 6.4 Verify Filtering

In **Kafdrop**, observe message flow:

Input:

```
sentrix.ingestor.events
```

Outputs:

```
sentrix.filter-service-a.cleaned
sentrix.filter-service-a.dropped
```

Messages should move automatically from ingestor to filter service A.

---

## 7. Sentiment Service (FastAPI)

### 7.1 Requirements

- Python 3.10+
- MongoDB Atlas access

---

### 7.2 MongoDB Atlas Access

Ask the project owner to:

- Invite your email to the MongoDB Atlas project
- Grant read/write permissions

---

### 7.3 Python Environment Setup

```bash
cd backend/sentiment-service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### 7.4 Environment Variables (.env file)

Create a `.env` file inside `sentiment-service`:

```env
MONGODB_URI=...
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
```

---

### 7.5 Run Sentiment Service

```bash
uvicorn app.main:app --reload --port 8001
```

Open API docs:

```
http://localhost:8001/docs
```

---

## 8. Filter Service B

Not implemented yet. No setup required.

---

## 9. Frontend (Next.js)

### 9.1 Setup

```bash
cd frontend
npm install
```

Create `.env`:

```env
NEXT_PUBLIC_FINNHUB_API_KEY=...
```

---

### 9.2 Run Frontend

```bash
npm run dev
```

Open:

```
http://localhost:3000
```

---

## 10. Debugging & Observability

### Kafka UI

```
http://localhost:9000
```

### Optional Kafka Consumer (Local Terminal)

```bash
/opt/homebrew/opt/kafka/bin/kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic sentrix.ingestor.events
```

---

## 11. Recommended Setup Order

1. Install global tools
2. Start Kafka
3. Create Kafka topics
4. Apply 7-day retention
5. Run ingestor service
6. Trigger ingestion
7. Run filter service A
8. Run sentiment service
9. Run frontend

---
