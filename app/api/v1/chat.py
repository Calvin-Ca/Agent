"""Unified chat endpoint — single API that understands user intent via LLM.

Replaces separate project/report/progress endpoints with one intelligent interface.
Accepts optional file upload + prompt, uses intent recognition to route to
the appropriate business logic.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import date

from fastapi import APIRouter, Form, UploadFile, File
from fastapi.responses import FileResponse
from loguru import logger
from sqlalchemy import select, func

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import BizError, NotFoundError
from app.core.response import R
from app.crud.project import project_crud
from app.crud.report import report_crud
from app.crud.document import document_crud
from app.db import minio
from app.models.document import Document
from app.models.progress import Progress
from app.schemas.chat import ChatResponse
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.schemas.report import ReportOut
from app.schemas.progress import ProgressOut
from app.schemas.upload import UploadOut

router = APIRouter(prefix="/chat", tags=["chat"])

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


@router.post("", summary="智能对话")
async def chat(
    db: DBSession,
    user: CurrentUser,
    prompt: str = Form(..., description="用户提示词"),
    project_id: str | None = Form(default=None, description="目标项目ID（可选）"),
    file: UploadFile | None = File(default=None, description="上传文件（可选）"),
):
    """Unified intelligent endpoint. Recognizes intent from prompt and executes."""
    from app.agents.graphs.router_graph import recognize_intent

    has_file = file is not None and file.filename
    intent_result = await asyncio.get_event_loop().run_in_executor(
        None, recognize_intent, prompt, project_id, bool(has_file),
    )

    intent = intent_result["intent"]
    params = intent_result.get("params", {})
    logger.info("Chat: user={} intent={} params={}", user.id, intent, params)

    # Resolve project_id: explicit param > intent-extracted > None
    resolved_project_id = project_id or params.get("project_id")

    # ── Route to handler ──────────────────────────────────────
    try:
        if intent == "create_project":
            return await _handle_create_project(db, user, params, prompt)

        elif intent == "list_projects":
            return await _handle_list_projects(db, user)

        elif intent == "update_project":
            return await _handle_update_project(db, user, resolved_project_id, params)

        elif intent == "delete_project":
            return await _handle_delete_project(db, user, resolved_project_id)

        elif intent == "record_progress":
            return await _handle_record_progress(db, user, resolved_project_id, params)

        elif intent == "list_progress":
            return await _handle_list_progress(db, user, resolved_project_id)

        elif intent == "generate_report":
            return await _handle_generate_report(user, db, resolved_project_id, params)

        elif intent == "list_reports":
            return await _handle_list_reports(db, user, resolved_project_id)

        elif intent == "get_report":
            return await _handle_get_report(db, user, params)

        elif intent == "export_report":
            return await _handle_export_report(db, user, params)

        elif intent == "upload_file":
            if not has_file:
                return R.ok(data=ChatResponse(
                    intent=intent,
                    message="请上传文件后重试。",
                ))
            return await _handle_upload_file(db, user, resolved_project_id, file)

        elif intent == "query":
            return await _handle_query(db, user, resolved_project_id, params, prompt)

        else:
            # Unknown intent — treat as query
            return await _handle_query(db, user, resolved_project_id, params, prompt)

    except NotFoundError as e:
        return R.ok(data=ChatResponse(intent=intent, message=str(e)))
    except BizError as e:
        return R.ok(data=ChatResponse(intent=intent, message=e.message))


# ══════════════════════════════════════════════════════════════
# Intent handlers
# ══════════════════════════════════════════════════════════════


async def _handle_create_project(db: DBSession, user: CurrentUser, params: dict, prompt: str):
    name = params.get("name", "")
    if not name:
        # Try to extract name from prompt
        return R.ok(data=ChatResponse(
            intent="create_project",
            message="请提供项目名称。例如：创建项目，名称：城南花园三期，编号：PRJ-001",
        ))

    code = params.get("code", "")
    description = params.get("description", "")

    body = ProjectCreate(name=name, code=code or name[:16], description=description)
    project = await project_crud.create(db, obj_in=body, owner_id=user.id)
    out = ProjectOut.model_validate(project)

    return R.ok(data=ChatResponse(
        intent="create_project",
        message=f"项目「{out.name}」创建成功！",
        data=out.model_dump(mode="json"),
    ))


async def _handle_list_projects(db: DBSession, user: CurrentUser):
    items, total = await project_crud.get_multi(
        db, page=1, page_size=50, filters={"owner_id": user.id},
    )
    projects = [ProjectOut.model_validate(i).model_dump(mode="json") for i in items]

    if not projects:
        msg = "您还没有创建任何项目。试试说「创建一个项目」。"
    else:
        msg = f"共有 {total} 个项目："
        for p in projects:
            status_map = {0: "进行中", 1: "暂停", 2: "已关闭"}
            msg += f"\n- {p['name']}（{p['code']}）— {status_map.get(p['status'], '未知')}"

    return R.ok(data=ChatResponse(
        intent="list_projects",
        message=msg,
        data=projects,
    ))


async def _handle_update_project(db: DBSession, user: CurrentUser, project_id: str | None, params: dict):
    if not project_id:
        return R.ok(data=ChatResponse(
            intent="update_project",
            message="请指定要更新的项目ID。",
        ))

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    update_data = {}
    if params.get("name"):
        update_data["name"] = params["name"]
    if params.get("description"):
        update_data["description"] = params["description"]
    if params.get("status") is not None:
        update_data["status"] = int(params["status"])

    if not update_data:
        return R.ok(data=ChatResponse(
            intent="update_project",
            message="未识别到要更新的内容，请说明要修改项目的哪些信息。",
        ))

    body = ProjectUpdate(**update_data)
    updated = await project_crud.update(db, id=project_id, obj_in=body)
    out = ProjectOut.model_validate(updated)

    return R.ok(data=ChatResponse(
        intent="update_project",
        message=f"项目「{out.name}」已更新。",
        data=out.model_dump(mode="json"),
    ))


async def _handle_delete_project(db: DBSession, user: CurrentUser, project_id: str | None):
    if not project_id:
        return R.ok(data=ChatResponse(
            intent="delete_project",
            message="请指定要删除的项目ID。",
        ))

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    name = project.name
    await project_crud.delete(db, id=project_id)

    return R.ok(data=ChatResponse(
        intent="delete_project",
        message=f"项目「{name}」已删除。",
    ))


async def _handle_record_progress(db: DBSession, user: CurrentUser, project_id: str | None, params: dict):
    if not project_id:
        return R.ok(data=ChatResponse(
            intent="record_progress",
            message="请指定项目ID以记录进度。",
        ))

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    overall_progress = float(params.get("overall_progress", 0))
    record = Progress(
        project_id=project_id,
        record_date=date.today(),
        overall_progress=overall_progress,
        milestone=params.get("milestone", ""),
        description=params.get("description", ""),
        blockers=params.get("blockers", ""),
        next_steps=params.get("next_steps", ""),
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    out = ProgressOut.model_validate(record)

    return R.ok(data=ChatResponse(
        intent="record_progress",
        message=f"已记录项目「{project.name}」的进度：{overall_progress}%",
        data=out.model_dump(mode="json"),
    ))


async def _handle_list_progress(db: DBSession, user: CurrentUser, project_id: str | None):
    if not project_id:
        return R.ok(data=ChatResponse(
            intent="list_progress",
            message="请指定项目ID以查看进度。",
        ))

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    base = select(Progress).where(Progress.project_id == project_id, Progress.is_deleted == False)  # noqa: E712
    count = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items_q = base.order_by(Progress.record_date.desc()).limit(20)
    items = (await db.execute(items_q)).scalars().all()
    progress_list = [ProgressOut.model_validate(i).model_dump(mode="json") for i in items]

    if not progress_list:
        msg = f"项目「{project.name}」暂无进度记录。"
    else:
        msg = f"项目「{project.name}」共有 {count} 条进度记录（最近20条）："
        for p in progress_list[:5]:
            msg += f"\n- [{p['record_date']}] 进度 {p['overall_progress']}%"
            if p.get("milestone"):
                msg += f" | {p['milestone']}"

    return R.ok(data=ChatResponse(
        intent="list_progress",
        message=msg,
        data=progress_list,
    ))


async def _handle_generate_report(user: CurrentUser, db: DBSession, project_id: str | None, params: dict):
    if not project_id:
        return R.ok(data=ChatResponse(
            intent="generate_report",
            message="请指定项目ID以生成周报。",
        ))

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    week_start = params.get("week_start", "")

    # Dispatch Celery task for async generation
    from app.tasks.report_tasks import generate_report_task
    task = generate_report_task.delay(
        project_id=project_id,
        user_id=user.id,
        week_start=week_start,
    )

    return R.ok(data=ChatResponse(
        intent="generate_report",
        message=f"已开始为项目「{project.name}」生成周报，任务ID: {task.id}",
        data={"task_id": task.id, "status": "generating"},
    ))


async def _handle_list_reports(db: DBSession, user: CurrentUser, project_id: str | None):
    filters = {"creator_id": user.id}
    if project_id:
        filters["project_id"] = project_id

    items, total = await report_crud.get_multi(db, page=1, page_size=20, filters=filters)
    reports = [ReportOut.model_validate(i).model_dump(mode="json") for i in items]

    if not reports:
        msg = "暂无周报记录。"
    else:
        msg = f"共有 {total} 份周报（最近20份）："
        for r in reports[:5]:
            msg += f"\n- {r['title']}"

    return R.ok(data=ChatResponse(
        intent="list_reports",
        message=msg,
        data=reports,
    ))


async def _handle_get_report(db: DBSession, user: CurrentUser, params: dict):
    report_id = params.get("report_id", "")
    if not report_id:
        return R.ok(data=ChatResponse(
            intent="get_report",
            message="请指定周报ID。可以先说「查看周报列表」获取ID。",
        ))

    report = await report_crud.get(db, id=report_id)
    if report is None or report.creator_id != user.id:
        raise NotFoundError("周报不存在")

    out = ReportOut.model_validate(report)
    return R.ok(data=ChatResponse(
        intent="get_report",
        message=f"周报「{out.title}」的内容如下：\n\n{out.content}",
        data=out.model_dump(mode="json"),
    ))


async def _handle_export_report(db: DBSession, user: CurrentUser, params: dict):
    report_id = params.get("report_id", "")
    if not report_id:
        return R.ok(data=ChatResponse(
            intent="export_report",
            message="请指定要导出的周报ID。",
        ))

    report = await report_crud.get(db, id=report_id)
    if report is None or report.creator_id != user.id:
        raise NotFoundError("周报不存在")

    fmt = params.get("format", "docx")
    from app.services.export_service import export_to_docx, export_to_markdown

    if fmt == "md":
        filepath = export_to_markdown(report.title, report.content)
        media_type = "text/markdown"
    else:
        filepath = export_to_docx(report.title, report.content)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return FileResponse(filepath, media_type=media_type, filename=filepath.split("/")[-1])


async def _handle_upload_file(db: DBSession, user: CurrentUser, project_id: str | None, file: UploadFile):
    if not project_id:
        return R.ok(data=ChatResponse(
            intent="upload_file",
            message="请指定项目ID以上传文件。",
        ))

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    # Validate file type
    content_type = file.content_type or ""
    file_type = _ALLOWED_TYPES.get(content_type)
    if file_type is None:
        return R.ok(data=ChatResponse(
            intent="upload_file",
            message=f"不支持的文件类型: {content_type}，支持: PDF, JPG, PNG, WebP, TXT, MD, CSV",
        ))

    # Read and validate size
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        return R.ok(data=ChatResponse(
            intent="upload_file",
            message="文件大小超过 50MB 限制。",
        ))

    # Dedup
    content_hash = hashlib.sha256(content).hexdigest()
    existing = await document_crud.get_by_hash(db, project_id=project_id, content_hash=content_hash)
    if existing:
        out = UploadOut.model_validate(existing)
        return R.ok(data=ChatResponse(
            intent="upload_file",
            message="文件已存在（去重），无需重复上传。",
            data=out.model_dump(mode="json"),
        ))

    # Upload to MinIO
    minio_key = f"uploads/{project_id}/{content_hash[:16]}_{file.filename}"
    await minio.upload_file(minio_key, content, content_type)

    # Create DB record
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

    # Dispatch async processing
    from app.tasks.document_tasks import process_document
    process_document.delay(doc.id)

    out = UploadOut.model_validate(doc)
    return R.ok(data=ChatResponse(
        intent="upload_file",
        message=f"文件「{file.filename}」上传成功，正在后台处理。",
        data=out.model_dump(mode="json"),
    ))


async def _handle_query(db: DBSession, user: CurrentUser, project_id: str | None, params: dict, prompt: str):
    if not project_id:
        return R.ok(data=ChatResponse(
            intent="query",
            message="请指定项目ID以进行查询。",
        ))

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    question = params.get("question", prompt)
    from app.services.progress_service import query_progress_sync

    result = await asyncio.get_event_loop().run_in_executor(
        None, query_progress_sync, project_id, user.id, question,
    )

    if not result["success"]:
        return R.ok(data=ChatResponse(
            intent="query",
            message=f"查询失败: {result.get('error', '未知错误')}",
        ))

    return R.ok(data=ChatResponse(
        intent="query",
        message=result["answer"],
        data={"answer": result["answer"]},
    ))
