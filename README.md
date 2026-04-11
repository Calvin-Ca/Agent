# Smart Weekly Report Agent

AI-powered agent system for automated weekly project report generation, progress tracking, and natural language querying over project data.

## Features

- **Automated report generation** — Upload site photos, PDFs, text data; the agent synthesizes a structured weekly report
- **Natural language progress queries** — Ask "XX项目进度如何？" and get answers backed by real project data
- **Multi-modal data processing** — Image OCR/VLM, PDF parsing, text chunking, vector embedding
- **RAG + SQL hybrid retrieval** — Combines structured database queries with semantic vector search
- **Streaming output** — Real-time report generation via WebSocket
- **High concurrency** — Redis caching, distributed locks, Celery async task queue

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Web Framework | FastAPI (async) |
| Agent Framework | LangChain + LangGraph |
| Database | MySQL 8.0 |
| Vector Store | Milvus 2.4 |
| Cache / Queue | Redis 7 + Celery |
| LLM | Ollama (Qwen2.5 / Llama3) |
| Embedding | BGE-large-zh-v1.5 |
| Object Storage | MinIO |

## Quick Start

```bash
# 1. Clone and configure
cp .env.example .env
# Edit .env with your settings

# 2. Start infrastructure
make up

# 3. Pull LLM models
make pull-models

# 4. Initialize databases
make db-init
make milvus-init

# 5. Run the application
make dev

# 6. Open Swagger docs
open http://localhost:8000/docs
```

## Project Structure

```
app/
├── main.py              # FastAPI entry point
├── config.py            # Centralized settings
├── api/v1/              # REST API routes
├── core/                # Exceptions, middleware, auth
├── models/              # SQLAlchemy ORM models
├── schemas/             # Pydantic request/response schemas
├── crud/                # Data access layer
├── agents/              # LangGraph agent workflows
│   ├── graph.py         # Main workflow definition
│   ├── nodes/           # Workflow step implementations
│   ├── tools/           # Agent-callable tools
│   └── prompts/         # Prompt templates
├── services/            # Business logic orchestration
├── pipeline/            # Data processing (PDF, image, text)
├── tasks/               # Celery async tasks
└── db/                  # Database connections
```

## Development

```bash
make lint    # Lint with ruff
make test    # Run tests with coverage
make fmt     # Auto-format code
```

## License

Private — Internal use only.
