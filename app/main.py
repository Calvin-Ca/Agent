"""FastAPI application entry point.

Lifespan manages startup/shutdown of:
- MySQL async engine
- Redis connection pool
- Milvus connection
- Tool registry (auto-discover built-in tools)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import uvicorn
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

    # Register built-in tools，注册内置工具
    from app.tools.registry import auto_discover_tools
    auto_discover_tools()

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
        description="Agent",
        docs_url="/docs" if settings.debug else None,  # 只有 debug=True 时才开放 Swagger 文档
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan, # 应用启动和关闭时执行的生命周期逻辑，比如初始化数据库、缓存、连接池等
    )

    # Register exception handlers
    register_exception_handlers(app)

    # Register middleware 
    # 中间件 = 在请求和响应之间“拦截并处理”的一层代码，可以
    # 日志记录：记录每个请求：谁访问了、访问了什么
    # 鉴权：检查 token 是否合法
    # 统一异常处理
    # 跨域（CORS）：允许前端访问后端
    # 性能统计：计算接口耗时
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

    # ── File Chat 模块（独立业务，无需鉴权）────────────────
    from app.api.file_chat.router import file_chat_router
    app.include_router(file_chat_router, prefix="/file_chat")

    return app


# Module-level app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
