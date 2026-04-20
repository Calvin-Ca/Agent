"""Project CRUD."""

from __future__ import annotations

from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectCRUD(CRUDBase[Project, ProjectCreate, ProjectUpdate]):

    async def get_by_name(
        self,
        db: AsyncSession,
        *,
        name: str,
        owner_id: str,
    ) -> Sequence[Project]:
        """Search projects by name (fuzzy LIKE match), scoped to owner.

        Returns matching projects ordered by most recently created.
        """
        stmt = (
            select(self.model)
            .where(
                self.model.is_deleted == False,  # noqa: E712
                self.model.owner_id == owner_id,
                self.model.name.contains(name),
            )
            .order_by(self.model.created_at.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()


project_crud = ProjectCRUD(Project)