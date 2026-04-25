"""Shared SQLAlchemy declarative base and common mixins."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _new_id() -> str:
    return uuid4().hex


class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models."""


class TimestampMixin:
    """Created/updated timestamps for mutable rows."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Soft-delete flag used by the generic CRUD helpers."""

    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


class IdMixin:
    """String primary key generated with UUID4 hex values."""

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id, nullable=False)
