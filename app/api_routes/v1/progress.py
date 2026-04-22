"""RESTful progress routes."""

from __future__ import annotations

from sqlalchemy import func, select

from fastapi import APIRouter

from app.api_routes.deps import CurrentUser, DBSession, Paging
from app.core.exceptions import NotFoundError
from app.core.response import PageData, R
from app.crud.project import project_crud
from app.models.progress import Progress
from app.schema_defs.progress import ProgressCreate, ProgressOut

router = APIRouter(prefix="/progress", tags=["progress"])


@router.post("", response_model=R[ProgressOut], summary="记录进度")
async def record_progress(body: ProgressCreate, db: DBSession, user: CurrentUser):
    project = await project_crud.get(db, id=body.project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    record = Progress(
        project_id=body.project_id,
        record_date=body.record_date,
        overall_progress=body.overall_progress,
        milestone=body.milestone or "",
        description=body.description or "",
        blockers=body.blockers or "",
        next_steps=body.next_steps or "",
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return R.ok(data=ProgressOut.model_validate(record))


@router.get("", response_model=R[PageData[ProgressOut]], summary="进度列表")
async def list_progress(project_id: str, db: DBSession, user: CurrentUser, paging: Paging):
    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    base = select(Progress).where(
        Progress.project_id == project_id,
        Progress.is_deleted == False,  # noqa: E712
    )
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items = (
        await db.execute(
            base.order_by(Progress.record_date.desc())
            .offset((paging.page - 1) * paging.page_size)
            .limit(paging.page_size)
        )
    ).scalars().all()

    return R.ok(
        data=PageData(
            items=[ProgressOut.model_validate(item) for item in items],
            total=total,
            page=paging.page,
            page_size=paging.page_size,
        )
    )
