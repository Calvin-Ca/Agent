#!/usr/bin/env python3
"""Initialize MySQL database — create all tables.

Usage:
    python scripts/init_db.py            # Create tables (skip existing)
    python scripts/init_db.py --reset    # DROP all tables first, then recreate

This is a quick bootstrap script for development.
In production, use Alembic migrations instead:
    alembic upgrade head
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text # sqlalchemy：用python代码操作数据库，而不是手写sql

from app.config import get_settings
from app.db.mysql import get_session_factory


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop all tables before creating")
    args = parser.parse_args()

    settings = get_settings()
    print(f"Connecting to MySQL: {settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")

    factory = get_session_factory()

    async with factory() as session:
        # Test connection
        result = await session.execute(text("SELECT 1")) # 把字符串 SQL 包装成 SQLAlchemy 可执行的 SQL 对象
        print(f"Connection OK: {result.scalar()}")

    # Import all models so SQLAlchemy registers them
    from app.models import Base  # noqa: F401 — triggers all model imports

    # Create all tables
    from app.db.mysql import _get_engine
    engine = _get_engine()

    # --reset: 先删除所有旧表，解决残留表 collation 不一致导致外键报错的问题
    if args.reset:
        print("Dropping all tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        print("All tables dropped")

    print("Creating tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # 自动创建所有 ORM 表（只要是继承base的）
    print("Tables created via metadata.create_all")

    # Verify
    async with factory() as session:
        result = await session.execute(text("SHOW TABLES"))
        tables = [row[0] for row in result.fetchall()]
        print(f"Tables: {tables}")

        # 验证每张表的 collation 是否一致（不一致会导致外键 incompatible 报错）
        for t in tables:
            r = await session.execute(text(
                "SELECT TABLE_COLLATION FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = :db AND TABLE_NAME = :tbl"
            ), {"db": settings.mysql_database, "tbl": t})
            print(f"  {t}: {r.scalar()}")

    print("\nDatabase initialization complete ✓")


if __name__ == "__main__":
    asyncio.run(main())