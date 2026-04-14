"""Report routes — generate, list, detail, export."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, DBSession, Paging
from app.core.exceptions import BizError, NotFoundError
from app.core.response import PageData, R
from app.crud.report import report_crud
from app.crud.project import project_crud
from app.schemas.report import ReportGenerate, ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/generate", response_model=R, summary="生成周报")
async def generate_report(
    body: ReportGenerate,
    user: CurrentUser,
    db: DBSession,
    background_tasks: BackgroundTasks,
):
    """Trigger weekly report generation (async via Celery)."""
    # Verify project
    project = await project_crud.get(db, id=body.project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    # Dispatch Celery task
    from app.tasks.report_tasks import generate_report_task
    task = generate_report_task.delay(
        project_id=body.project_id,
        user_id=user.id,
        week_start=body.week_start.isoformat() if body.week_start else "",
    )

    return R.ok(data={"task_id": task.id, "status": "generating"}, message="周报生成已启动")


@router.post("/generate-sync", response_model=R[ReportOut], summary="同步生成周报")
async def generate_report_sync(body: ReportGenerate, user: CurrentUser, db: DBSession):
    """Generate report synchronously (blocks until done). For testing."""
    project = await project_crud.get(db, id=body.project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    from app.services.report_service import generate_report_sync as gen_sync
    import asyncio

    result = await asyncio.get_event_loop().run_in_executor(
        None, gen_sync, body.project_id, user.id,
        body.week_start.isoformat() if body.week_start else "",
    )

    if not result["success"]:
        raise BizError(code=50001, message=f"生成失败: {result['error']}")

    report = await report_crud.get(db, id=result["report_id"])
    return R.ok(data=ReportOut.model_validate(report))


@router.get("", response_model=R[PageData[ReportOut]], summary="周报列表")
async def list_reports(
    db: DBSession, user: CurrentUser, paging: Paging,
    project_id: str | None = None,
):
    filters = {"creator_id": user.id}
    if project_id:
        filters["project_id"] = project_id

    items, total = await report_crud.get_multi(
        db, page=paging.page, page_size=paging.page_size, filters=filters,
    )
    return R.ok(data=PageData(
        items=[ReportOut.model_validate(i) for i in items],
        total=total, page=paging.page, page_size=paging.page_size,
    ))


@router.get("/{report_id}", response_model=R[ReportOut], summary="周报详情")
async def get_report(report_id: str, db: DBSession, user: CurrentUser):
    report = await report_crud.get(db, id=report_id)
    if report is None or report.creator_id != user.id:
        raise NotFoundError("周报不存在")
    return R.ok(data=ReportOut.model_validate(report))


@router.get("/{report_id}/export", summary="导出周报")
async def export_report(
    report_id: str, db: DBSession, user: CurrentUser,
    format: str = "docx",
):
    """Export report as .docx or .md file."""
    report = await report_crud.get(db, id=report_id)
    if report is None or report.creator_id != user.id:
        raise NotFoundError("周报不存在")

    from app.services.export_service import export_to_docx, export_to_markdown

    if format == "md":
        filepath = export_to_markdown(report.title, report.content)
        media_type = "text/markdown"
    else:
        filepath = export_to_docx(report.title, report.content)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    return FileResponse(filepath, media_type=media_type, filename=filepath.split("/")[-1])