"""Progress record ORM model."""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class Progress(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "progress_records"

    project_id: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    record_date: Mapped[date] = mapped_column(Date, index=True, nullable=False)
    overall_progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    milestone: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    blockers: Mapped[str] = mapped_column(Text, default="", nullable=False)
    next_steps: Mapped[str] = mapped_column(Text, default="", nullable=False)
