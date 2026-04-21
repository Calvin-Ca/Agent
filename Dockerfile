FROM python:3.11-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gcc \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-chi-sim && \
    rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app/ app/
COPY agent/ agent/
COPY core/ core/
COPY llm/ llm/
COPY memory/ memory/
COPY tools/ tools/
COPY output/ output/
COPY infra/ infra/
COPY prompts/ prompts/
COPY evals/ evals/
COPY tests/ tests/
COPY scripts/ scripts/
COPY migrations/ migrations/
COPY alembic.ini ./

RUN pip install --upgrade pip && pip install .

FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    tesseract-ocr \
    tesseract-ocr-chi-sim && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local /usr/local
COPY . .

RUN mkdir -p storage/uploads storage/exports logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
