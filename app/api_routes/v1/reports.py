"""RESTful report routes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api_routes.deps import CurrentUser, DBSession, Paging
from app.core.exceptions import NotFoundError
from app.core.response import PageData, R
from app.crud.project import project_crud
from app.crud.report import report_crud
from agent.infra.logger import get_log_context
from app.schema_defs.report import ReportGenerate, ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate", response_model=R, summary="生成周报")
async def generate_report(body: ReportGenerate, db: DBSession, user: CurrentUser):
    project = await project_crud.get(db, id=body.project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    from app.tasks.report_tasks import generate_report_task

    log_context = get_log_context()
    task = generate_report_task.delay(
        project_id=body.project_id,
        user_id=user.id,
        week_start=body.week_start.isoformat() if body.week_start else "",
        request_id=log_context["request_id"],
        request_log_file=log_context["request_log_file"],
    )
    return R.ok(data={"task_id": task.id, "status": "generating"})


@router.get("", response_model=R[PageData[ReportOut]], summary="周报列表")
async def list_reports(
    db: DBSession,
    user: CurrentUser,
    paging: Paging,
    project_id: str | None = None,
):
    filters = {"creator_id": user.id}
    if project_id:
        filters["project_id"] = project_id

    items, total = await report_crud.get_multi(
        db, page=paging.page, page_size=paging.page_size, filters=filters,
    )
    return R.ok(
        data=PageData(
            items=[ReportOut.model_validate(item) for item in items],
            total=total,
            page=paging.page,
            page_size=paging.page_size,
        )
    )


@router.get("/{report_id}", response_model=R[ReportOut], summary="周报详情")
async def get_report(report_id: str, db: DBSession, user: CurrentUser):
    report = await report_crud.get(db, id=report_id)
    if report is None or report.creator_id != user.id:
        raise NotFoundError("周报不存在")
    return R.ok(data=ReportOut.model_validate(report))


@router.get("/{report_id}/export", summary="导出周报")
async def export_report(report_id: str, db: DBSession, user: CurrentUser, fmt: str = "docx"):
    report = await report_crud.get(db, id=report_id)
    if report is None or report.creator_id != user.id:
        raise NotFoundError("周报不存在")

    from agent.tools.builtin.file_manager import export_to_docx, export_to_markdown

    if fmt == "md":
        filepath = export_to_markdown(report.title, report.content)
        media_type = "text/markdown"
    else:
        filepath = export_to_docx(report.title, report.content)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return FileResponse(filepath, media_type=media_type, filename=filepath.split("/")[-1])
