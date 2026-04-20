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
from app.observability.logger import get_log_context, run_in_executor_with_context
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

# Intents that do NOT require a project to be resolved
_NO_PROJECT_INTENTS = {"create_project", "list_projects", "list_reports", "get_report", "export_report"}


@router.post("", summary="智能对话")
async def chat(
    db: DBSession,
    user: CurrentUser,
    prompt: str = Form(..., description="用户提示词"),
    file: UploadFile | None = File(default=None, description="上传文件（可选）"),
):
    """Unified intelligent endpoint. Recognizes intent from prompt and executes."""
    import time as _time
    from app.agents.graphs.router_graph import recognize_intent

    chat_start = _time.perf_counter()

    has_file = file is not None and file.filename
    logger.info(
        "[Chat] 收到请求 | user={} prompt='{}' has_file={}",
        user.id, prompt[:100], bool(has_file),
    )

    intent_result = await run_in_executor_with_context(
        asyncio.get_event_loop(),
        recognize_intent,
        prompt,
        bool(has_file),
    )

    intent = intent_result["intent"]
    params = intent_result.get("params", {})
    logger.info("[Chat] 意图识别 | user={} intent={} params={}", user.id, intent, params)

    # ── Resolve project_name → project_id ─────────────────────
    resolved_project_id = None
    if intent not in _NO_PROJECT_INTENTS:
        project_name = params.get("project_name", "")
        if project_name:
            resolved_project_id = await _resolve_project_id(db, user.id, project_name, intent)

    # ── Route to handler ──────────────────────────────────────
    try:
        if intent == "create_project":
            result = await _handle_create_project(db, user, params, prompt)

        elif intent == "list_projects":
            result = await _handle_list_projects(db, user)

        elif intent == "update_project":
            result = await _handle_update_project(db, user, resolved_project_id, params)

        elif intent == "delete_project":
            result = await _handle_delete_project(db, user, resolved_project_id)

        elif intent == "record_progress":
            result = await _handle_record_progress(db, user, resolved_project_id, params)

        elif intent == "list_progress":
            result = await _handle_list_progress(db, user, resolved_project_id)

        elif intent == "generate_report":
            result = await _handle_generate_report(user, db, resolved_project_id, params)

        elif intent == "list_reports":
            # list_reports supports optional project filtering by name
            project_name = params.get("project_name", "")
            filter_project_id = None
            if project_name:
                filter_project_id = await _resolve_project_id(db, user.id, project_name, intent)
            result = await _handle_list_reports(db, user, filter_project_id)

        elif intent == "get_report":
            result = await _handle_get_report(db, user, params)

        elif intent == "export_report":
            result = await _handle_export_report(db, user, params)

        elif intent == "upload_file":
            if not has_file:
                result = R.ok(data=ChatResponse(
                    intent=intent,
                    message="请上传文件后重试。",
                ))
            else:
                result = await _handle_upload_file(db, user, resolved_project_id, file)

        elif intent == "query":
            result = await _handle_query(db, user, resolved_project_id, params, prompt)

        else:
            # Unknown intent — treat as query
            result = await _handle_query(db, user, resolved_project_id, params, prompt)

    except NotFoundError as e:
        result = R.ok(data=ChatResponse(intent=intent, message=str(e)))
    except BizError as e:
        result = R.ok(data=ChatResponse(intent=intent, message=e.message))

    elapsed_ms = (_time.perf_counter() - chat_start) * 1000
    logger.info(
        "[Chat] 完成 | user={} intent={} elapsed={:.0f}ms",
        user.id, intent, elapsed_ms,
    )
    return result


# ══════════════════════════════════════════════════════════════
# Project name → ID resolution
# ══════════════════════════════════════════════════════════════


async def _resolve_project_id(
    db: DBSession,
    owner_id: str,
    project_name: str,
    intent: str,
) -> str | None:
    """Resolve a user-provided project name to a project ID.

    Uses fuzzy (LIKE) matching, returns the best match (most recently created).
    Returns None if no match is found (caller decides how to handle).
    """
    matches = await project_crud.get_by_name(db, name=project_name, owner_id=owner_id)

    if not matches:
        logger.info("[Resolve] 未找到项目 | name='{}' owner={}", project_name, owner_id)
        return None

    if len(matches) == 1:
        project = matches[0]
        logger.info("[Resolve] 匹配项目 | name='{}' → id={} ({})", project_name, project.id, project.name)
        return project.id

    # Multiple matches — prefer exact match, otherwise pick the most recent
    for p in matches:
        if p.name == project_name:
            logger.info("[Resolve] 精确匹配 | name='{}' → id={}", project_name, p.id)
            return p.id

    project = matches[0]  # already ordered by created_at desc
    logger.info(
        "[Resolve] 模糊匹配({}个候选) | name='{}' → id={} ({})",
        len(matches), project_name, project.id, project.name,
    )
    return project.id


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
            message="未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
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
            message="未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
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
            message="未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
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
            message="未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
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
            message="未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
        ))

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    week_start = params.get("week_start", "")

    # Dispatch Celery task for async generation
    from app.tasks.report_tasks import generate_report_task
    log_context = get_log_context()
    task = generate_report_task.delay(
        project_id=project_id,
        user_id=user.id,
        week_start=week_start,
        request_id=log_context["request_id"],
        request_log_file=log_context["request_log_file"],
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
            message="未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
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
    log_context = get_log_context()
    process_document.delay(
        document_id=doc.id,
        user_id=str(user.id),
        request_id=log_context["request_id"],
        request_log_file=log_context["request_log_file"],
    )

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
            message="未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
        ))

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    question = params.get("question", prompt)
    from app.services.progress_service import query_progress_sync

    result = await run_in_executor_with_context(
        asyncio.get_event_loop(),
        query_progress_sync,
        project_id,
        user.id,
        question,
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
