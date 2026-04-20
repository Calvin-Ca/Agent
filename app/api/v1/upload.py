"""Upload routes — receive files, store metadata, dispatch processing."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, UploadFile, File, Form

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import BizError, NotFoundError
from app.core.response import R
from app.crud.document import document_crud
from app.crud.project import project_crud
from app.db import minio
from app.models.document import Document
from app.observability.logger import get_log_context
from app.schemas.upload import UploadOut

router = APIRouter(prefix="/upload", tags=["upload"])

_ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "text/plain": "text",
    "text/markdown": "text",
    "text/csv": "text",
}
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


@router.post("", response_model=R[UploadOut], summary="上传文件")
async def upload_file(
    db: DBSession,
    user: CurrentUser,
    project_id: str = Form(...),
    file: UploadFile = File(...),
):
    # 1. Validate project
    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    # 2. Validate file type
    content_type = file.content_type or ""
    file_type = _ALLOWED_TYPES.get(content_type)
    if file_type is None:
        raise BizError(
            code=40010,
            message=f"不支持的文件类型: {content_type}，支持: PDF, JPG, PNG, WebP, TXT, MD, CSV",
        )

    # 3. Read file content
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise BizError(code=40011, message="文件大小超过 50MB 限制")

    # 4. Hash for dedup
    content_hash = hashlib.sha256(content).hexdigest()
    existing = await document_crud.get_by_hash(db, project_id=project_id, content_hash=content_hash)
    if existing:
        return R.ok(data=UploadOut.model_validate(existing), message="文件已存在（去重）")

    # 5. Upload to MinIO
    minio_key = f"uploads/{project_id}/{content_hash[:16]}_{file.filename}"
    await minio.upload_file(minio_key, content, content_type)

    # 6. Create DB record
    doc = Document(
        project_id=project_id,
        filename=file.filename or "unnamed",
        file_type=file_type,
        file_path=minio_key,  # MinIO object key
        file_size=len(content),
        content_hash=content_hash,
        process_status=0,  # pending
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # 7. Dispatch async processing task via Celery
    from app.tasks.document_tasks import process_document
    log_context = get_log_context()
    process_document.delay(
        document_id=doc.id,
        user_id=str(user.id),
        request_id=log_context["request_id"],
        request_log_file=log_context["request_log_file"],
    )

    return R.ok(data=UploadOut.model_validate(doc), message="上传成功，等待处理")
