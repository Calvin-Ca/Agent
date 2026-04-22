"""Report-related business operations."""

from __future__ import annotations

from fastapi.responses import FileResponse

from app.api_routes.deps import CurrentUser, DBSession
from app.core.exceptions import NotFoundError
from app.core.response import R
from app.crud.project import project_crud
from app.crud.report import report_crud
from agent.infra.logger import get_log_context
from app.schema_defs.chat import ChatResponse
from app.schema_defs.report import ReportOut


def _chat_response(intent: str, message: str, data: dict | list | None = None):
    return R.ok(data=ChatResponse(intent=intent, message=message, data=data))


def _missing_project_response(intent: str):
    return _chat_response(
        intent,
        "未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
    )


async def handle_generate_report(
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


async def handle_list_reports(db: DBSession, user: CurrentUser, project_id: str | None):
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


async def handle_get_report(db: DBSession, user: CurrentUser, params: dict):
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


async def handle_export_report(db: DBSession, user: CurrentUser, params: dict):
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
