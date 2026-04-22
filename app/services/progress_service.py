"""Progress-related business operations."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app.api_routes.deps import CurrentUser, DBSession
from app.core.exceptions import NotFoundError
from app.core.response import R
from app.crud.project import project_crud
from app.models.progress import Progress
from app.schema_defs.chat import ChatResponse
from app.schema_defs.progress import ProgressOut


def _chat_response(intent: str, message: str, data: dict | list | None = None):
    return R.ok(data=ChatResponse(intent=intent, message=message, data=data))


def _missing_project_response(intent: str):
    return _chat_response(
        intent,
        "未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
    )


async def handle_record_progress(
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


async def handle_list_progress(db: DBSession, user: CurrentUser, project_id: str | None):
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
