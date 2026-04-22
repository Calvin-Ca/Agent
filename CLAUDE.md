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

### Two Core Workflows (LangGraph state machines in `agent/core/workflows/`)

**1. Report Generation** (`POST /api/v1/reports/generate` or via chat):
```
Planner → DataCollector → ReportWriter → ReportReviewer → MySQL/MinIO export
```
- DataCollector fetches structured data from MySQL + semantic search from Milvus
- ReportReviewer can trigger rewrites (self-review loop)
- Output: Markdown stored in MySQL, exported to DOCX/PDF via MinIO

**2. Natural Language Query** (`POST /api/v1/chat` with query intent):
```
Planner → DataCollector → ProgressQuery → answer
```

### Key Module Boundaries

| Layer | Location | Responsibility |
|---|---|---|
| API routes | `app/api_routes/v1/` | HTTP endpoints (auth, chat, projects, progress, reports, documents) |
| Services | `app/services/` | Business logic split by domain (project, progress, report, document, query) |
| Agent workflows | `agent/core/workflows/` | LangGraph state machines (query + report) |
| Shared nodes | `agent/core/nodes.py` | Workflow nodes: data_collector, writer, reviewer, query |
| Data access | `app/crud/` | SQLAlchemy repository pattern |
| LLM backends | `agent/llm/` | LLM/embedding/VLM abstraction (vLLM/Ollama/OpenAI/Anthropic) |
| Memory system | `agent/memory/` | Working, cache, long-term (Milvus), structured (MySQL) |
| Tool system | `agent/tools/` | Registry + executor + builtin tools (db_query, file_manager) |
| Input processing | `agent/input/` | PDF/image extraction, intent routing, guardrails |
| Async tasks | `app/tasks/` | Celery document processing and report generation |
| DB connections | `app/db/` | MySQL (aiomysql), Redis, Milvus, MinIO clients |
| Infrastructure | `agent/infra/` | Config, metrics, tracing, logging, middleware |

### API Endpoints

Two styles of API access:
- **Chat endpoint** (`POST /api/v1/chat`): Natural language → intent recognition → dispatch
- **RESTful endpoints**: Direct CRUD without NL parsing
  - `/api/v1/projects` — Project CRUD
  - `/api/v1/progress` — Progress record/list
  - `/api/v1/reports` — Report generate/list/get/export
  - `/api/v1/documents` — Document upload

### Model Backend Registry (`agent/llm/registry.py`)
Three interchangeable backends configured via `.env`:
- `vllm` — vLLM OpenAI-compatible endpoint (production)
- `ollama` — HTTP inference (flexible CPU/GPU)
- `openai` / `anthropic` — cloud API fallbacks

### Database Roles
- **MySQL**: structured data — Users, Projects, Reports, Progress, Documents
- **Milvus**: document embeddings for semantic search (BGE-large-zh-v1.5 / bge-m3, dim=1024)
- **Redis**: caching (db=0) + Celery broker (db=1) + results (db=2)
- **MinIO**: object storage for uploaded files and exported reports

## Configuration

Settings are loaded from `.env` via `agent/infra/config.py` (Pydantic Settings), re-exported through `app/config.py`. Key env groups:
- `MYSQL_*`, `REDIS_*`, `MILVUS_*`, `MINIO_*` — service connections
- `BACKEND`, `LLM_API_BASE`, `OLLAMA_*` — model backend selection
- `EMBED_API_BASE`, `EMBED_MODEL_NAME` — embedding model
- `JWT_*` — authentication

## Tech Stack

- Python 3.10+, FastAPI 0.115, SQLAlchemy async (aiomysql)
- LangChain + LangGraph for agent orchestration
- Milvus 2.4, Redis 5, Celery
- PyMuPDF + pdfplumber (PDF), PaddleOCR (images)
- Ruff for linting/formatting (line-length 120)
- pytest + pytest-asyncio for tests
