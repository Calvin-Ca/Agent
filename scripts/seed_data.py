#!/usr/bin/env python3
"""Seed demo data for development and testing.

Usage:
    python scripts/seed_data.py
"""

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text # text() 用来写“原生 SQL”字符串，并让 SQLAlchemy 正确识别它是 SQL 语句，而不是普通字符串。

from app.config import get_settings
from app.core.security import hash_password
from app.db.mysql import get_session_factory, close_mysql
from app.models import Base, User, Project, Progress


async def main() -> None:
    settings = get_settings()
    print(f"Seeding data into {settings.mysql_database}...")

    factory = get_session_factory()

    async with factory() as db:
        # ── Demo User ────────────────────────────────────────
        existing = await db.execute(
            text("SELECT id FROM users WHERE username = 'caic'")
        )
        if existing.scalar():
            print("Demo user already exists, skipping seed.")
            await close_mysql()
            return

        user = User(
            username="caic",
            email="caic@example.com",
            hashed_password=hash_password("caic"),
            nickname="CaiC",
            role=1,
        )
        db.add(user)
        await db.flush()
        print(f"Created user: caic / caic (id={user.id})")

        # ── Demo Projects ────────────────────────────────────
        projects_data = [
            ("城南花园三期", "PRJ-001", "住宅项目，共12栋，地下2层"),
            ("科技园B区改造", "PRJ-002", "办公楼改造升级工程"),
            ("滨江大桥维修", "PRJ-003", "桥梁结构检测与加固维修"),
        ]
        projects = []
        for name, code, desc in projects_data:
            p = Project(name=name, code=code, description=desc, owner_id=user.id, status=1)
            db.add(p)
            projects.append(p)
        await db.flush()
        print(f"Created {len(projects)} demo projects")

        # ── Demo Progress Records ────────────────────────────
        today = date.today()
        for i, project in enumerate(projects):
            for week in range(4):
                d = today - timedelta(weeks=3 - week)
                progress_val = min(100, (week + 1) * 20 + i * 5)
                rec = Progress(
                    project_id=project.id,
                    record_date=d,
                    overall_progress=progress_val,
                    milestone=f"第{week+1}周里程碑",
                    description=f"本周完成了基础设施建设第{week+1}阶段",
                    blockers="天气影响施工进度" if week == 1 else "",
                    next_steps=f"下周计划推进第{week+2}阶段工作",
                )
                db.add(rec)

        await db.commit()
        print("Created progress records (4 weeks x 3 projects)")

    await close_mysql()
    print("\nSeed complete ✓")
    print("Login with: username=caic, password=caic")


if __name__ == "__main__":
    asyncio.run(main())