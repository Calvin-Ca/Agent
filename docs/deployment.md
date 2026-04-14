# Deployment Guide

## Architecture Overview

```
                    ┌─────────────────┐
                    │   Nginx / CDN   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  FastAPI (8000)  │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
       ┌──────▼──────┐ ┌────▼────┐ ┌──────▼──────┐
       │ Celery Worker│ │  Redis  │ │   MySQL     │
       └──────┬──────┘ └─────────┘ └─────────────┘
              │
       ┌──────▼──────┐
       │   Milvus    │
       └─────────────┘

Model Services (separate machine / GPU server):
       ┌─────────────┐  ┌─────────────┐
       │ vLLM LLM    │  │ vLLM Embed  │
       │ (port 8001) │  │ (port 8002) │
       └─────────────┘  └─────────────┘
```

## Prerequisites

- Docker + Docker Compose
- Python 3.11+
- GPU server with vLLM for model services

## Step 1: Model Services (GPU Server)

```bash
# On GPU server
cd smart-weekly-report
conda activate vlm
pip install -r models/requirements.txt

# Edit models/serve.py SERVICES config, then:
python models/serve.py start
python models/serve.py test
```

## Step 2: Infrastructure (App Server)

```bash
# Start MySQL, Redis, Milvus
make up

# Initialize databases
python scripts/init_db.py --reset
python scripts/init_milvus.py
python scripts/seed_data.py
```

## Step 3: Application

### Development

```bash
cp .env.example .env
# Edit .env: set LLM_API_BASE, EMBED_API_BASE to GPU server

make dev        # Terminal 1: FastAPI
make worker     # Terminal 2: Celery worker
make beat       # Terminal 3: Celery beat (optional)
```

### Production (Docker)

```bash
docker compose up -d app worker beat
```

## Step 4: Verify

```bash
# Health check
curl http://localhost:8000/health

# Swagger UI
open http://localhost:8000/docs

# Run tests
make test
```

## Environment Configurations

### Local Development (.env)
```env
LLM_BACKEND=api
LLM_API_BASE=http://127.0.0.1:8001/v1
EMBED_BACKEND=api
EMBED_API_BASE=http://127.0.0.1:8002/v1
```

### Production (.env)
```env
DEBUG=false
SECRET_KEY=<random-64-char>
LLM_BACKEND=api
LLM_API_BASE=http://gpu-server:8001/v1
EMBED_BACKEND=api
EMBED_API_BASE=http://gpu-server:8002/v1
```

## SSH Tunnel (if no direct network access)

```bash
ssh -L 8001:127.0.0.1:8001 -L 8002:127.0.0.1:8002 user@gpu-server -N
```

## Monitoring

- FastAPI: http://localhost:8000/docs
- Milvus: http://localhost:9091/healthz
- MinIO Console: http://localhost:9001
- Celery: check worker logs via `make worker`