"""Progress routes — record and query project progress."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession, Paging
from app.core.exceptions import NotFoundError
from app.core.response import PageData, R
from app.crud.project import project_crud
from app.models.progress import Progress
from app.schemas.progress import ProgressCreate, ProgressOut

router = APIRouter(prefix="/progress", tags=["progress"])


@router.post("", response_model=R[ProgressOut], summary="记录进度")
async def create_progress(body: ProgressCreate, db: DBSession, user: CurrentUser):
    # Verify project ownership
    project = await project_crud.get(db, id=body.project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    record = Progress(
        project_id=body.project_id,
        record_date=body.record_date or date.today(),
        overall_progress=body.overall_progress,
        milestone=body.milestone,
        description=body.description,
        blockers=body.blockers,
        next_steps=body.next_steps,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return R.ok(data=ProgressOut.model_validate(record))


@router.get("", response_model=R[PageData[ProgressOut]], summary="进度列表")
async def list_progress(
    project_id: str,
    db: DBSession,
    user: CurrentUser,
    paging: Paging,
):
    # Verify project ownership
    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    from sqlalchemy import select, func
    from app.models.progress import Progress as PM

    base = select(PM).where(PM.project_id == project_id, PM.is_deleted == False)  # noqa
    count = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    items_q = base.order_by(PM.record_date.desc()).offset(
        (paging.page - 1) * paging.page_size
    ).limit(paging.page_size)
    items = (await db.execute(items_q)).scalars().all()

    return R.ok(
        data=PageData(
            items=[ProgressOut.model_validate(i) for i in items],
            total=count,
            page=paging.page,
            page_size=paging.page_size,
        )
    )


# POST /progress/query (natural language) will be added in P4