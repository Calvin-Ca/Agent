# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Smart Weekly Report Agent** — An AI-powered system for automated weekly project report generation and natural language progress queries. Built with FastAPI + LangGraph orchestration, MySQL + Milvus (vector DB), and flexible LLM backends (local/API/Ollama).

## Common Commands

All commands via `Makefile`:

```bash
# Infrastructure
make up               # Start all 8 Docker services
make down             # Stop all services
make logs             # Tail service logs

# Development
make dev              # FastAPI dev server with hot reload (app listens on port 7777)
make worker           # Start Celery worker
make beat             # Start Celery beat scheduler

# Database
make db-init          # Run Alembic migrations
make db-migrate msg="description"  # Generate new migration
make milvus-init      # Initialize Milvus collections

# Code quality
make lint             # Ruff check + auto-fix
make fmt              # Ruff format (line-length 120)
make test             # pytest with coverage

# Run a single test
pytest tests/test_api/test_auth.py -v
pytest tests/ -k "test_name" -v
```

## Architecture

### Two Core Workflows (LangGraph state machines in `app/agents/`)

**1. Report Generation** (`/api/v1/reports/generate`):
```
Planner → DataCollector → ReportWriter → ReportReviewer → MySQL/MinIO export
```
- DataCollector fetches structured data from MySQL + semantic search from Milvus
- ReportReviewer can trigger rewrites (self-review loop)
- Output: Markdown stored in MySQL, exported to DOCX/PDF via MinIO

**2. Natural Language Query** (`/api/v1/progress/query`):
```
Planner → DataCollector → ProgressQuery → answer
```

### Key Module Boundaries

| Layer | Location | Responsibility |
|---|---|---|
| API routes | `app/api/v1/` | HTTP endpoints, request validation |
| Agent workflows | `app/agents/` | LangGraph state machines, prompt templates |
| Business logic | `app/services/` | Domain operations |
| Data access | `app/crud/` | SQLAlchemy repository pattern |
| Model services | `app/model_service/` | LLM/embedding/VLM abstraction (local/API/Ollama backends) |
| Data pipelines | `app/pipeline/` | PDF/image OCR → chunk → embed → Milvus |
| Async tasks | `app/tasks/` | Celery document processing queue |
| DB connections | `app/db/` | MySQL (aiomysql), Redis, Milvus clients |

### Model Backend Registry (`app/model_service/registry.py`)
Three interchangeable backends configured via `.env`:
- `local` — direct transformers loading
- `api` — vLLM/TGI OpenAI-compatible endpoint (production)
- `ollama` — HTTP inference (flexible CPU/GPU)

### Database Roles
- **MySQL**: structured data — Users, Projects, Reports, Progress, Documents
- **Milvus**: document embeddings for semantic search (BGE-large-zh-v1.5 / bge-m3, dim=1024)
- **Redis**: caching (db=0) + Celery broker (db=1) + results (db=2)
- **MinIO**: object storage for uploaded files and exported reports

## Configuration

Settings are loaded from `.env` via `app/config.py` (Pydantic Settings). Key env groups:
- `MYSQL_*`, `REDIS_*`, `MILVUS_*`, `MINIO_*` — service connections
- `LLM_BACKEND`, `LLM_API_BASE`, `OLLAMA_*` — model backend selection
- `EMBED_MODEL_PATH`, `EMBED_BACKEND` — embedding model
- `JWT_*` — authentication

## Tech Stack

- Python 3.11+, FastAPI 0.115, SQLAlchemy async (aiomysql)
- LangChain + LangGraph for agent orchestration
- Milvus 2.4, Redis 5, Celery
- PyMuPDF + pdfplumber (PDF), PaddleOCR (images)
- Ruff for linting/formatting (line-length 120)
- pytest + pytest-asyncio for tests
