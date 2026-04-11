"""MySQL async connection via SQLAlchemy 2.0 async engine.

Usage in FastAPI dependency:
    async def get_db() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_factory() as session:
            yield session
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

# SQLAlchemy 是一个 Python 的 ORM（对象关系映射）库，用于简化数据库操作。
# 它支持多种数据库（如 MySQL、PostgreSQL），提供同步和异步 API，用于构建 SQL 查询、事务管理和数据模型映射。
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings

_engine: AsyncEngine | None = None   # 声明一个私有变量，类型为 AsyncEngine 或 None，初始值为 None。
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.mysql_dsn,
            pool_size=20,
            max_overflow=10,
            pool_recycle=3600,
            pool_pre_ping=True,
            echo=settings.debug,
        )
    return _engine

# python模块在第一次import时，会执行一次代码，并缓存到sys.modules
def get_session_factory() -> async_sessionmaker[AsyncSession]: # 负责生成session，一个session是一次工作周期：创建session、执行增删改查、commit/rollback、关闭session
    global _session_factory  
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=_get_engine(),   # 绑定数据库引擎
            class_=AsyncSession,  # 指定session为异步版本
            expire_on_commit=False,
        )
    return _session_factory
# python import <module>流程
# 查 sys.modules中有没有 <module>，有就直接复用，没有就执行下一步
# 加载模块：执行这个 <module>文件的所有代码，注意只有在第一次import时会执行一次，后面import不会再执行！
# 创建一个 <module> 对象并存入 sys.modules


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session, auto-closes."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_mysql() -> None:
    """Graceful shutdown — call in FastAPI lifespan."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
