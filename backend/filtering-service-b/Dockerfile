FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip setuptools wheel

COPY requirements.docker.txt ./
RUN pip install -r requirements.docker.txt

COPY src ./src


FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    HOST=0.0.0.0 \
    PORT=8012 \
    HF_HOME=/tmp/hf-cache \
    TRANSFORMERS_CACHE=/tmp/hf-cache \
    SENTENCE_TRANSFORMERS_HOME=/tmp/hf-cache \
    TORCH_HOME=/tmp/hf-cache

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY src ./src

EXPOSE 8012

CMD ["python", "-m", "filtering_service_b.main"]
