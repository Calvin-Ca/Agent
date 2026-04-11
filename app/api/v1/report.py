"""Report routes — list, detail, generate (generation logic in P3/P4)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession, Paging
from app.core.exceptions import NotFoundError
from app.core.response import PageData, R
from app.crud.report import report_crud
from app.schemas.report import ReportOut

router = APIRouter(prefix="/reports", tags=["reports"])


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
            items=[ReportOut.model_validate(i) for i in items],
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


# POST /reports/generate will be added in P4 (agent integration)