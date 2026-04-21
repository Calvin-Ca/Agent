"""Chat service — unified product-facing business orchestration."""

from __future__ import annotations

import asyncio
import hashlib
import time
from datetime import date

from fastapi import UploadFile
from fastapi.responses import FileResponse
from loguru import logger
from sqlalchemy import func, select

from app.api_routes.deps import CurrentUser, DBSession
from app.core.exceptions import BizError, NotFoundError
from app.core.response import R
from app.crud.document import document_crud
from app.crud.project import project_crud
from app.crud.report import report_crud
from app.db import minio
from app.models.document import Document
from app.models.progress import Progress
from agent.core.state import AgentState
from agent.infra.logger import get_log_context, run_in_executor_with_context
from app.schema_defs.chat import ChatResponse
from app.schema_defs.progress import ProgressOut
from app.schema_defs.project import ProjectCreate, ProjectOut, ProjectUpdate
from app.schema_defs.report import ReportOut
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
_NO_PROJECT_INTENTS = {
    "create_project",
    "list_projects",
    "list_reports",
    "get_report",
    "export_report",
}


async def handle_chat(
    db: DBSession,
    user: CurrentUser,
    state: AgentState,
    file: UploadFile | None = None,
):
    """Dispatch to the matching product action using the pre-resolved AgentState.

    Intent recognition is performed upstream by AgentLoop.prepare_state() via
    IntentRouter, so we read intent/params directly from ``state`` without
    calling the LLM a second time.
    """
    started_at = time.perf_counter()
    intent = state.intent
    params = state.params
    has_file = file is not None and bool(file.filename)
    logger.info(
        "[Chat] 分派请求 | user={} intent={} params={} has_file={}",
        user.id,
        intent,
        params,
        bool(has_file),
    )

    resolved_project_id = None
    if intent not in _NO_PROJECT_INTENTS:
        project_name = params.get("project_name", "")
        if project_name:
            resolved_project_id = await _resolve_project_id(db, user.id, project_name)

    try:
        if intent == "create_project":
            result = await _handle_create_project(db, user, params)
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
            filter_project_id = None
            project_name = params.get("project_name", "")
            if project_name:
                filter_project_id = await _resolve_project_id(db, user.id, project_name)
            result = await _handle_list_reports(db, user, filter_project_id)
        elif intent == "get_report":
            result = await _handle_get_report(db, user, params)
        elif intent == "export_report":
            result = await _handle_export_report(db, user, params)
        elif intent == "upload_file":
            if not has_file:
                result = _chat_response(intent, "请上传文件后重试。")
            else:
                result = await _handle_upload_file(db, user, resolved_project_id, file)
        else:
            result = await _handle_query(db, user, resolved_project_id, params, prompt)
    except NotFoundError as exc:
        result = _chat_response(intent, str(exc))
    except BizError as exc:
        result = _chat_response(intent, exc.message)

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "[Chat] 完成 | user={} intent={} elapsed={:.0f}ms",
        user.id,
        intent,
        elapsed_ms,
    )
    return result


def _chat_response(intent: str, message: str, data: dict | list | None = None):
    return R.ok(data=ChatResponse(intent=intent, message=message, data=data))


def _missing_project_response(intent: str):
    return _chat_response(
        intent,
        "未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
    )


async def _resolve_project_id(
    db: DBSession,
    owner_id: str,
    project_name: str,
) -> str | None:
    """Resolve a project name to the best-matching project id."""
    matches = await project_crud.get_by_name(db, name=project_name, owner_id=owner_id)

    if not matches:
        logger.info("[Resolve] 未找到项目 | name='{}' owner={}", project_name, owner_id)
        return None

    if len(matches) == 1:
        project = matches[0]
        logger.info("[Resolve] 匹配项目 | name='{}' → id={} ({})", project_name, project.id, project.name)
        return project.id

    for project in matches:
        if project.name == project_name:
            logger.info("[Resolve] 精确匹配 | name='{}' → id={}", project_name, project.id)
            return project.id

    project = matches[0]
    logger.info(
        "[Resolve] 模糊匹配({}个候选) | name='{}' → id={} ({})",
        len(matches),
        project_name,
        project.id,
        project.name,
    )
    return project.id


async def _handle_create_project(db: DBSession, user: CurrentUser, params: dict):
    name = params.get("name", "")
    if not name:
        return _chat_response(
            "create_project",
            "请提供项目名称。例如：创建项目，名称：城南花园三期，编号：PRJ-001",
        )

    body = ProjectCreate(
        name=name,
        code=params.get("code", "") or name[:16],
        description=params.get("description", ""),
    )
    project = await project_crud.create(db, obj_in=body, owner_id=user.id)
    out = ProjectOut.model_validate(project)
    return _chat_response(
        "create_project",
        f"项目「{out.name}」创建成功！",
        out.model_dump(mode="json"),
    )


async def _handle_list_projects(db: DBSession, user: CurrentUser):
    items, total = await project_crud.get_multi(
        db,
        page=1,
        page_size=50,
        filters={"owner_id": user.id},
    )
    projects = [ProjectOut.model_validate(item).model_dump(mode="json") for item in items]

    if not projects:
        message = "您还没有创建任何项目。试试说「创建一个项目」。"
    else:
        status_map = {0: "进行中", 1: "暂停", 2: "已关闭"}
        lines = [
            f"- {project['name']}（{project['code']}）— {status_map.get(project['status'], '未知')}"
            for project in projects
        ]
        message = f"共有 {total} 个项目：\n" + "\n".join(lines)

    return _chat_response("list_projects", message, projects)


async def _handle_update_project(
    db: DBSession,
    user: CurrentUser,
    project_id: str | None,
    params: dict,
):
    if not project_id:
        return _missing_project_response("update_project")

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
        return _chat_response(
            "update_project",
            "未识别到要更新的内容，请说明要修改项目的哪些信息。",
        )

    updated = await project_crud.update(db, id=project_id, obj_in=ProjectUpdate(**update_data))
    out = ProjectOut.model_validate(updated)
    return _chat_response(
        "update_project",
        f"项目「{out.name}」已更新。",
        out.model_dump(mode="json"),
    )


async def _handle_delete_project(db: DBSession, user: CurrentUser, project_id: str | None):
    if not project_id:
        return _missing_project_response("delete_project")

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    await project_crud.delete(db, id=project_id)
    return _chat_response("delete_project", f"项目「{project.name}」已删除。")


async def _handle_record_progress(
    db: DBSession,
    user: CurrentUser,
    project_id: str | None,
    params: dict,
):
    if not project_id:
        return _missing_project_response("record_progress")

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    record = Progress(
        project_id=project_id,
        record_date=date.today(),
        overall_progress=float(params.get("overall_progress", 0)),
        milestone=params.get("milestone", ""),
        description=params.get("description", ""),
        blockers=params.get("blockers", ""),
        next_steps=params.get("next_steps", ""),
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    out = ProgressOut.model_validate(record)
    return _chat_response(
        "record_progress",
        f"已记录项目「{project.name}」的进度：{out.overall_progress}%",
        out.model_dump(mode="json"),
    )


async def _handle_list_progress(db: DBSession, user: CurrentUser, project_id: str | None):
    if not project_id:
        return _missing_project_response("list_progress")

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    base = select(Progress).where(
        Progress.project_id == project_id,
        Progress.is_deleted == False,  # noqa: E712
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (
        await db.execute(base.order_by(Progress.record_date.desc()).limit(20))
    ).scalars().all()
    progress_list = [ProgressOut.model_validate(item).model_dump(mode="json") for item in items]

    if not progress_list:
        message = f"项目「{project.name}」暂无进度记录。"
    else:
        lines = [f"- [{item['record_date']}] 进度 {item['overall_progress']}%" for item in progress_list[:5]]
        message = f"项目「{project.name}」共有 {total} 条进度记录（最近20条）：\n" + "\n".join(lines)

    return _chat_response("list_progress", message, progress_list)


async def _handle_generate_report(
    user: CurrentUser,
    db: DBSession,
    project_id: str | None,
    params: dict,
):
    if not project_id:
        return _missing_project_response("generate_report")

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    from app.tasks.report_tasks import generate_report_task

    log_context = get_log_context()
    task = generate_report_task.delay(
        project_id=project_id,
        user_id=user.id,
        week_start=params.get("week_start", ""),
        request_id=log_context["request_id"],
        request_log_file=log_context["request_log_file"],
    )
    return _chat_response(
        "generate_report",
        f"已开始为项目「{project.name}」生成周报，任务ID: {task.id}",
        {"task_id": task.id, "status": "generating"},
    )


async def _handle_list_reports(db: DBSession, user: CurrentUser, project_id: str | None):
    filters = {"creator_id": user.id}
    if project_id:
        filters["project_id"] = project_id

    items, total = await report_crud.get_multi(db, page=1, page_size=20, filters=filters)
    reports = [ReportOut.model_validate(item).model_dump(mode="json") for item in items]

    if not reports:
        message = "暂无周报记录。"
    else:
        titles = "\n".join(f"- {report['title']}" for report in reports[:5])
        message = f"共有 {total} 份周报（最近20份）：\n{titles}"

    return _chat_response("list_reports", message, reports)


async def _handle_get_report(db: DBSession, user: CurrentUser, params: dict):
    report_id = params.get("report_id", "")
    if not report_id:
        return _chat_response("get_report", "请指定周报ID。可以先说「查看周报列表」获取ID。")

    report = await report_crud.get(db, id=report_id)
    if report is None or report.creator_id != user.id:
        raise NotFoundError("周报不存在")

    out = ReportOut.model_validate(report)
    return _chat_response(
        "get_report",
        f"周报「{out.title}」的内容如下：\n\n{out.content}",
        out.model_dump(mode="json"),
    )


async def _handle_export_report(db: DBSession, user: CurrentUser, params: dict):
    report_id = params.get("report_id", "")
    if not report_id:
        return _chat_response("export_report", "请指定要导出的周报ID。")

    report = await report_crud.get(db, id=report_id)
    if report is None or report.creator_id != user.id:
        raise NotFoundError("周报不存在")

    from agent.tools.builtin.file_manager import export_to_docx, export_to_markdown

    fmt = params.get("format", "docx")
    if fmt == "md":
        filepath = export_to_markdown(report.title, report.content)
        media_type = "text/markdown"
    else:
        filepath = export_to_docx(report.title, report.content)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return FileResponse(filepath, media_type=media_type, filename=filepath.split("/")[-1])


async def _handle_upload_file(
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


async def _handle_query(
    db: DBSession,
    user: CurrentUser,
    project_id: str | None,
    params: dict,
    prompt: str,
):
    if not project_id:
        return _missing_project_response("query")

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    from agent.core.react_engine import query_workflow

    result = await run_in_executor_with_context(
        asyncio.get_event_loop(),
        query_workflow.run,
        project_id,
        user.id,
        params.get("question", prompt),
    )

    if not result["success"]:
        return _chat_response(
            "query",
            f"查询失败: {result.get('error', '未知错误')}",
        )

    return _chat_response("query", result["answer"], {"answer": result["answer"]})
