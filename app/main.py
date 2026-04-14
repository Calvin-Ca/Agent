"""FastAPI application entry point.

Lifespan manages startup/shutdown of:
- MySQL async engine
- Redis connection pool
- Milvus connection
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from loguru import logger

from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_middleware
from app.core.response import R
from app.db.milvus import connect_milvus, disconnect_milvus
from app.db.mysql import close_mysql, get_session_factory
from app.db.redis import close_redis, get_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    settings = get_settings()
    logger.info("Starting {} (env={})", settings.app_name, settings.app_env)

    # ── Startup ──────────────────────────────────────────────
    # Touch session factory to initialize the engine + pool
    get_session_factory()
    logger.info("MySQL pool initialized")

    # Warm up Redis connection
    redis = get_redis()
    await redis.ping()
    logger.info("Redis connected")

    # Connect Milvus
    try:
        connect_milvus()
    except Exception as e:
        logger.warning("Milvus not available at startup (non-fatal): {}", e)

    logger.info("All services ready ✓")

    yield

    # ── Shutdown ─────────────────────────────────────────────
    logger.info("Shutting down...")
    await close_mysql()
    await close_redis()
    disconnect_milvus()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="AI agent for automated weekly project report generation",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    # Register exception handlers
    register_exception_handlers(app)

    # Register middleware
    register_middleware(app)

    # ── Health check ─────────────────────────────────────────
    @app.get("/health", tags=["infra"])
    async def health_check() -> R:
        return R.ok(data={"status": "healthy", "env": settings.app_env})

    # ── Register routers ─────────────────────────────────────
    from app.api.v1.router import v1_router
    app.include_router(v1_router, prefix=settings.api_v1_prefix)

    from app.api.websocket import router as ws_router
    app.include_router(ws_router)

    return app


# Module-level app instance for uvicorn
app = create_app()