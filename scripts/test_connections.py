#!/usr/bin/env python3
"""Connectivity smoke tests for MySQL, Redis, Milvus.

Usage:
    # Test all services
    python scripts/test_connections.py

    # Test individual service
    python scripts/test_connections.py mysql
    python scripts/test_connections.py redis
    python scripts/test_connections.py milvus
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Colors for terminal output ───────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {CYAN}→{RESET} {msg}")


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")
    print("─" * 50)


# ── MySQL Tests ──────────────────────────────────────────────

async def test_mysql() -> bool:
    section("MySQL")
    passed = True

    from app.config import get_settings
    settings = get_settings()
    info(f"DSN: mysql+aiomysql://{settings.mysql_user}:***@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_database}")

    # 1. Connection
    try:
        from app.db.mysql import get_session_factory, close_mysql
        factory = get_session_factory()
        ok("Engine + session factory created")
    except Exception as e:
        fail(f"Engine creation failed: {e}")
        return False

    # 2. Basic query
    try:
        from sqlalchemy import text
        async with factory() as session:
            result = await session.execute(text("SELECT 1 AS ping"))
            val = result.scalar()
            assert val == 1
            ok("SELECT 1 → OK")
    except Exception as e:
        fail(f"Basic query failed: {e}")
        passed = False

    # 3. Database version
    try:
        async with factory() as session:
            result = await session.execute(text("SELECT VERSION()"))
            version = result.scalar()
            ok(f"MySQL version: {version}")
    except Exception as e:
        fail(f"Version query failed: {e}")
        passed = False

    # 4. Character set check
    try:
        async with factory() as session:
            result = await session.execute(
                text("SELECT DEFAULT_CHARACTER_SET_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = :db"),
                {"db": settings.mysql_database},
            )
            charset = result.scalar()
            if charset == "utf8mb4":
                ok(f"Character set: {charset}")
            else:
                fail(f"Character set is '{charset}', expected 'utf8mb4'")
                passed = False
    except Exception as e:
        fail(f"Charset check failed: {e}")
        passed = False

    # 5. Write + read + cleanup
    try:
        async with factory() as session:
            await session.execute(text(
                "CREATE TABLE IF NOT EXISTS _conn_test (id INT PRIMARY KEY, val VARCHAR(50))"
            ))
            await session.execute(text(
                "REPLACE INTO _conn_test (id, val) VALUES (1, '你好世界')"
            ))
            await session.commit()

            result = await session.execute(text("SELECT val FROM _conn_test WHERE id = 1"))
            val = result.scalar()
            assert val == "你好世界"
            ok("Write + read (中文 UTF-8) → OK")

            await session.execute(text("DROP TABLE _conn_test"))
            await session.commit()
            ok("Cleanup → OK")
    except Exception as e:
        fail(f"Write/read test failed: {e}")
        passed = False

    # 6. Connection pool stats
    try:
        from app.db.mysql import _engine
        if _engine and _engine.pool:
            pool = _engine.pool
            ok(f"Pool size: {pool.size()}, checked out: {pool.checkedout()}")
    except Exception:
        pass

    await close_mysql()
    return passed


# ── Redis Tests ──────────────────────────────────────────────

async def test_redis() -> bool:
    section("Redis")
    passed = True

    from app.config import get_settings
    settings = get_settings()
    info(f"URL: redis://{settings.redis_host}:{settings.redis_port}/{settings.redis_db}")

    # 1. Ping
    try:
        from app.db.redis import get_redis, close_redis
        r = get_redis()
        pong = await r.ping()
        assert pong is True
        ok("PING → PONG")
    except Exception as e:
        fail(f"Ping failed: {e}")
        return False

    # 2. Server info
    try:
        info_data = await r.info("server")
        ok(f"Redis version: {info_data.get('redis_version', 'unknown')}")
    except Exception as e:
        fail(f"INFO failed: {e}")
        passed = False

    # 3. SET / GET / DEL
    try:
        test_key = "_conn_test:hello"
        await r.set(test_key, "你好世界", ex=60)
        val = await r.get(test_key)
        assert val == "你好世界"
        ok("SET + GET (中文) → OK")
        await r.delete(test_key)
        ok("DEL → OK")
    except Exception as e:
        fail(f"SET/GET test failed: {e}")
        passed = False

    # 4. Cache helpers
    try:
        from app.db.redis import cache_set, cache_get, cache_delete

        test_data = {"project": "测试项目", "progress": 85.5, "tags": ["AI", "报告"]}
        await cache_set("_conn_test:json", test_data, ttl=60)
        retrieved = await cache_get("_conn_test:json")
        assert retrieved == test_data
        ok("JSON cache helpers (set/get) → OK")

        await cache_delete("_conn_test:json")
        assert await cache_get("_conn_test:json") is None
        ok("Cache delete → OK")
    except Exception as e:
        fail(f"Cache helper test failed: {e}")
        passed = False

    # 5. Distributed lock
    try:
        from app.db.redis import distributed_lock

        async with distributed_lock("_conn_test:lock", timeout=5) as acquired:
            assert acquired is True
            ok("Distributed lock acquire → OK")

            # Try to acquire same lock again (should fail)
            async with distributed_lock("_conn_test:lock", timeout=5, blocking_timeout=1) as second:
                if not second:
                    ok("Lock re-entry blocked → OK (expected)")
                else:
                    fail("Lock was acquired twice — this shouldn't happen")
                    passed = False
    except Exception as e:
        fail(f"Distributed lock test failed: {e}")
        passed = False

    # 6. Latency benchmark
    try:
        rounds = 100
        start = time.perf_counter()
        for i in range(rounds):
            await r.set(f"_conn_test:bench:{i}", i, ex=10)
        elapsed = (time.perf_counter() - start) * 1000
        ok(f"Latency: {rounds} SET ops in {elapsed:.0f}ms ({elapsed/rounds:.1f}ms/op)")

        # cleanup
        from app.db.redis import cache_delete_pattern
        deleted = await cache_delete_pattern("_conn_test:*")
        ok(f"Pattern cleanup: {deleted} keys deleted")
    except Exception as e:
        fail(f"Benchmark failed: {e}")
        passed = False

    # 7. Memory info
    try:
        mem_info = await r.info("memory")
        used_mb = int(mem_info.get("used_memory", 0)) / 1024 / 1024
        ok(f"Memory used: {used_mb:.1f} MB")
    except Exception:
        pass

    await close_redis()
    return passed


# ── Milvus Tests ─────────────────────────────────────────────

def test_milvus() -> bool:
    section("Milvus")
    passed = True

    from app.config import get_settings
    settings = get_settings()
    info(f"Host: {settings.milvus_host}:{settings.milvus_port}")
    info(f"Collection: {settings.milvus_collection} (dim={settings.milvus_dim})")

    # 1. Connect
    try:
        from app.db.milvus import connect_milvus, disconnect_milvus
        connect_milvus()
        ok("Connection established")
    except Exception as e:
        fail(f"Connection failed: {e}")
        return False

    # 2. List collections
    try:
        from pymilvus import utility
        collections = utility.list_collections()
        ok(f"Existing collections: {collections or '(none)'}")
    except Exception as e:
        fail(f"List collections failed: {e}")
        passed = False

    # 3. Create / get collection
    try:
        from app.db.milvus import get_or_create_collection
        collection = get_or_create_collection()
        ok(f"Collection '{collection.name}' ready ({collection.num_entities} entities)")
    except Exception as e:
        fail(f"Collection creation failed: {e}")
        return False

    # 4. Schema verification
    try:
        fields = {f.name: f.dtype.name for f in collection.schema.fields}
        expected = {"id", "project_id", "document_id", "chunk_index", "content", "embedding"}
        if expected.issubset(fields.keys()):
            ok(f"Schema fields: {list(fields.keys())}")
        else:
            missing = expected - fields.keys()
            fail(f"Missing fields: {missing}")
            passed = False
    except Exception as e:
        fail(f"Schema check failed: {e}")
        passed = False

    # 5. Index verification
    try:
        indexes = collection.indexes
        if indexes:
            idx = indexes[0]
            ok(f"Index: {idx.params}")
        else:
            fail("No index found on collection")
            passed = False
    except Exception as e:
        fail(f"Index check failed: {e}")
        passed = False

    # 6. Insert + search + delete test vector
    try:
        import random
        dim = settings.milvus_dim
        test_vector = [random.random() for _ in range(dim)]

        insert_data = [
            ["test_project_000"],           # project_id
            ["test_doc_000"],               # document_id
            [0],                            # chunk_index
            ["这是一条连接测试数据"],          # content
            [test_vector],                  # embedding
        ]
        mr = collection.insert(insert_data)
        inserted_id = mr.primary_keys[0]
        ok(f"Insert test vector → ID: {inserted_id}")

        # Flush to make it searchable
        collection.flush()

        # Search
        from app.db.milvus import search_vectors
        results = search_vectors(
            collection,
            query_embedding=test_vector,
            project_id="test_project_000",
            top_k=1,
            score_threshold=0.0,
        )
        if results and results[0]["content"] == "这是一条连接测试数据":
            ok(f"Search → found (score={results[0]['score']})")
        else:
            fail("Search returned unexpected results")
            passed = False

        # Delete test data
        collection.delete(f'id in [{inserted_id}]')
        collection.flush()
        ok("Cleanup test vector → OK")
    except Exception as e:
        fail(f"Insert/search test failed: {e}")
        passed = False

    disconnect_milvus()
    return passed


# ── Main ─────────────────────────────────────────────────────

async def main() -> None:
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["mysql", "redis", "milvus"]

    print(f"\n{BOLD}{'=' * 50}{RESET}")
    print(f"{BOLD}  Smart Weekly Report — Connection Tests{RESET}")
    print(f"{BOLD}{'=' * 50}{RESET}")

    from app.config import get_settings
    settings = get_settings()
    info(f"Environment: {settings.app_env}")

    results: dict[str, bool] = {}

    if "mysql" in targets:
        results["MySQL"] = await test_mysql()

    if "redis" in targets:
        results["Redis"] = await test_redis()

    if "milvus" in targets:
        results["Milvus"] = test_milvus()

    # Summary
    section("Summary")
    all_passed = True
    for name, passed in results.items():
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {name:10s} {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print(f"  {GREEN}{BOLD}All tests passed ✓{RESET}")
    else:
        print(f"  {RED}{BOLD}Some tests failed ✗{RESET}")
        print(f"  {YELLOW}Check the .env file and make sure services are running (make up){RESET}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main()) # 创建事件循环、运行main()协程、执行完后关闭事件循环

# 事件循环（（Event Loop）：单线程中一个不断检查任务、执行任务、切换任务的调度器
# 伪代码
# while True：
#   检查有没有任务可以执行，
#  执行任务，
# 遇到await则挂起，切换到其它任务
