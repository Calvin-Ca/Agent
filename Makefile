.PHONY: help dev up down logs worker beat db-init db-migrate seed seed-knowledge migrate-db lint fmt test eval

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Infrastructure ───────────────────────────────────────────
up:  ## Start all Docker services
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

seed-knowledge:  ## Ingest local knowledge into long-term memory
	python scripts/seed_knowledge.py

migrate-db:  ## Apply Alembic migrations through the helper script
	python scripts/migrate_db.py

# ── Quality ──────────────────────────────────────────────────
lint:  ## Lint with ruff
	ruff check app/ tests/ --fix

fmt:  ## Format with ruff
	ruff format app/ tests/

test:  ## Run tests
	pytest -v --cov=app --cov=agent --cov=core --cov=llm --cov=memory --cov=tools --cov-report=term-missing

eval:  ## Run lightweight offline evals
	python -m evals.eval_runner
