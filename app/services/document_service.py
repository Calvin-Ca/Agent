"""Document upload business operations."""

from __future__ import annotations

import hashlib

from fastapi import UploadFile

from app.api_routes.deps import CurrentUser, DBSession
from app.core.exceptions import NotFoundError
from app.core.response import R
from app.crud.document import document_crud
from app.crud.project import project_crud
from app.db import minio
from app.models.document import Document
from agent.infra.logger import get_log_context
from app.schema_defs.chat import ChatResponse
from app.schema_defs.upload import UploadOut

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


def _chat_response(intent: str, message: str, data: dict | list | None = None):
    return R.ok(data=ChatResponse(intent=intent, message=message, data=data))


def _missing_project_response(intent: str):
    return _chat_response(
        intent,
        "未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
    )


async def handle_upload_file(
    db: DBSession,
    user: CurrentUser,
    project_id: str | None,
    file: UploadFile,
):
    if not project_id:
        return _missing_project_response("upload_file")

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    content_type = file.content_type or ""
    file_type = _ALLOWED_TYPES.get(content_type)
    if file_type is None:
        return _chat_response(
            "upload_file",
            f"不支持的文件类型: {content_type}，支持: PDF, JPG, PNG, WebP, TXT, MD, CSV",
        )

    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        return _chat_response("upload_file", "文件大小超过 50MB 限制。")

    content_hash = hashlib.sha256(content).hexdigest()
    existing = await document_crud.get_by_hash(db, project_id=project_id, content_hash=content_hash)
    if existing:
        out = UploadOut.model_validate(existing)
        return _chat_response(
            "upload_file",
            "文件已存在（去重），无需重复上传。",
            out.model_dump(mode="json"),
        )

    minio_key = f"uploads/{project_id}/{content_hash[:16]}_{file.filename}"
    await minio.upload_file(minio_key, content, content_type)

    doc = Document(
        project_id=project_id,
        filename=file.filename or "unnamed",
        file_type=file_type,
        file_path=minio_key,
        file_size=len(content),
        content_hash=content_hash,
        process_status=0,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    from app.tasks.document_tasks import process_document

    log_context = get_log_context()
    process_document.delay(
        document_id=doc.id,
        user_id=str(user.id),
        request_id=log_context["request_id"],
        request_log_file=log_context["request_log_file"],
    )

    out = UploadOut.model_validate(doc)
    return _chat_response(
        "upload_file",
        f"文件「{file.filename}」上传成功，正在后台处理。",
        out.model_dump(mode="json"),
    )
