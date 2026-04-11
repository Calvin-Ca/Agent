.PHONY: help dev up down db-init milvus-init seed lint test

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
dev:  ## Run dev server with hot reload
	uvicorn app.main:app --reload --host 0.0.0.0 --port 7777

worker:  ## Start Celery worker
	celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2

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
pull-models:  ## Pull default Ollama models
	docker compose exec ollama ollama pull qwen2.5:14b
	docker compose exec ollama ollama pull bge-large-zh-v1.5
