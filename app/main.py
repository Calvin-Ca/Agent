"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from loguru import logger

from app.api import router as api_router
from app.api_routes.v1.router import v1_router
from app.api_routes.websocket import router as ws_router
from app.dependencies import get_container
from app.core.exceptions import register_exception_handlers
from app.core.middleware import register_middleware
from app.db.milvus import connect_milvus, disconnect_milvus
from app.db.mysql import close_mysql, get_session_factory
from app.db.redis import close_redis, get_redis
from agent.infra.config import get_settings
from agent.infra.logger import setup_logging
from agent.infra.metrics import make_metrics_app
from agent.infra.tracing import init_tracer


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup / shutdown lifecycle."""
    settings = get_settings()
    _ = get_container()
    setup_logging(
        log_level="DEBUG" if settings.debug else "INFO",
        json_output=settings.app_env == "production",
    )
    init_tracer(service_name=settings.app_name)
    logger.info("Starting {} (env={})", settings.app_name, settings.app_env)

    get_session_factory()
    logger.info("Database engine initialized")

    try:
        redis = get_redis()
        await redis.ping()
        logger.info("Redis connected")
    except Exception as exc:
        logger.warning("Redis not available at startup (non-fatal): {}", exc)

    try:
        connect_milvus()
        logger.info("Milvus connected")
    except Exception as exc:
        logger.warning("Milvus not available at startup (non-fatal): {}", exc)

    try:
        from agent.tools.registry import auto_discover_tools

        auto_discover_tools()
    except Exception as exc:
        logger.warning("Tool discovery skipped at startup: {}", exc)

    try:
        from agent.llm.registry import auto_discover_models

        auto_discover_models()
    except Exception as exc:
        logger.warning("Model registry init skipped at startup: {}", exc)

    logger.info("All services ready ✓")

    yield

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
        description="Agent platform",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan,
    )

    register_exception_handlers(app)
    register_middleware(app)

    app.include_router(api_router)
    app.include_router(v1_router, prefix=settings.api_v1_prefix)
    app.include_router(ws_router)

    metrics_asgi = make_metrics_app()
    if metrics_asgi:
        app.mount("/metrics", metrics_asgi)
        logger.info("Prometheus /metrics endpoint enabled")

    return app


# Module-level app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
