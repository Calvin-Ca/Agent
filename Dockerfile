# 再把 FastAPI 项目打包成镜像
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libmariadb-dev curl tesseract-ocr tesseract-ocr-chi-sim && \
    rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install .

# App code
COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini ./
COPY scripts/ scripts/

# Create storage dirs
RUN mkdir -p storage/uploads storage/exports logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]