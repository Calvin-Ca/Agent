"""Project CRUD."""

from __future__ import annotations

from app.crud.base import CRUDBase
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectCRUD(CRUDBase[Project, ProjectCreate, ProjectUpdate]):
    pass


project_crud = ProjectCRUD(Project)