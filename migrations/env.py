"""Alembic migration environment.

Reads the database URL from app.config so there's a single source of truth.
"""

from __future__ import annotations

import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make project root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings

# Import the declarative Base so Alembic can detect models
# Models will be added here in P1:
# from app.models.base import Base
# from app.models import user, project, document, report, progress

# Placeholder until P1
from sqlalchemy.orm import DeclarativeBase


class _TempBase(DeclarativeBase):
    pass


target_metadata = _TempBase.metadata

config = context.config

# Override sqlalchemy.url from app settings
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.mysql_dsn_sync)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without connecting."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — connects and applies directly."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
