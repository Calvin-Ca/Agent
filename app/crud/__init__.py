"""Package placeholder — implementation in later phases."""
"""CRUD data access layer."""

from app.crud.user import user_crud
from app.crud.project import project_crud
from app.crud.report import report_crud
from app.crud.document import document_crud

__all__ = ["user_crud", "project_crud", "report_crud", "document_crud"]
