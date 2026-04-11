"""Document CRUD with hash-based dedup."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.document import Document
from app.schemas.upload import UploadOut


class _DocUpdate:
    pass


class DocumentCRUD(CRUDBase[Document, UploadOut, _DocUpdate]):

    async def get_by_hash(
        self, db: AsyncSession, *, project_id: str, content_hash: str
    ) -> Document | None:
        """Find existing document by content hash (dedup)."""
        stmt = select(Document).where(
            Document.project_id == project_id,
            Document.content_hash == content_hash,
            Document.is_deleted == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


document_crud = DocumentCRUD(Document)