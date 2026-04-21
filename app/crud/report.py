"""Report CRUD with week-based queries."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.report import Report
from app.schema_defs.report import ReportGenerate, ReportOut


class _ReportUpdate:
    """Placeholder — reports are updated via service layer, not direct CRUD."""
    pass


class ReportCRUD(CRUDBase[Report, ReportGenerate, _ReportUpdate]):

    async def get_by_project_week(
        self, db: AsyncSession, *, project_id: str, week_start: date
    ) -> Report | None:
        stmt = select(Report).where(
            Report.project_id == project_id,
            Report.week_start == week_start,
            Report.is_deleted == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


report_crud = ReportCRUD(Report)