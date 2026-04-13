.PHONY: help dev up down db-init milvus-init seed lint test

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Infrastructure ───────────────────────────────────────────
up:  ## Start all Docker services
	bash scripts/init_dirs.sh
	docker compose up -d

down:  ## Stop all Docker services
	docker compose down

logs:  ## Tail all service logs
	docker compose logs -f --tail=50

# ── Application ──────────────────────────────────────────────
# GPU device (override: make dev GPU=0,1)
GPU ?= 1

dev:  ## Run dev server with hot reload
	CUDA_VISIBLE_DEVICES=$(GPU) uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:  ## Start Celery worker
	CUDA_VISIBLE_DEVICES=$(GPU) celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2

beat:  ## Start Celery beat scheduler
	celery -A app.tasks.celery_app beat --loglevel=info

# ── Database / Init ──────────────────────────────────────────
db-init:  ## Create DB tables via Alembic
	alembic upgrade head

db-migrate:  ## Generate new migration
	alembic revision --autogenerate -m "$(msg)"

milvus-init:  ## Create Milvus collections
	python scripts/init_milvus.py

seed:  ## Seed test data
	python scripts/seed_data.py

# ── Quality ──────────────────────────────────────────────────
lint:  ## Lint with ruff
	ruff check app/ tests/ --fix

fmt:  ## Format with ruff
	ruff format app/ tests/

test:  ## Run tests
	pytest -v --cov=app --cov-report=term-missing

# ── Models ───────────────────────────────────────────────────
model-start:  ## Start all model services (vLLM)
	bash models/serve.sh start

model-stop:  ## Stop all model services
	bash models/serve.sh stop

model-status:  ## Show model service status
	bash models/serve.sh status

model-test:  ## Test model API endpoints
	bash models/serve.sh test

model-logs:  ## Tail model logs (usage: make model-logs SVC=llm)
	bash models/serve.sh logs $(SVC)