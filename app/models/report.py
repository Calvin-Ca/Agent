"""Weekly report ORM model."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Report(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "reports"

    project_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    creator_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    week_start: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    export_path: Mapped[str] = mapped_column(String(512), default="", nullable=False)
