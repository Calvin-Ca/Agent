"""Project CRUD routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession, Paging
from app.core.exceptions import NotFoundError
from app.core.response import PageData, R
from app.crud.project import project_crud
from app.schemas.project import ProjectCreate, ProjectOut, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=R[ProjectOut], summary="创建项目")
async def create_project(body: ProjectCreate, db: DBSession, user: CurrentUser):
    project = await project_crud.create(db, obj_in=body, owner_id=user.id)
    return R.ok(data=ProjectOut.model_validate(project))


@router.get("", response_model=R[PageData[ProjectOut]], summary="项目列表")
async def list_projects(db: DBSession, user: CurrentUser, paging: Paging):
    items, total = await project_crud.get_multi(
        db,
        page=paging.page,
        page_size=paging.page_size,
        filters={"owner_id": user.id},
    )
    return R.ok(
        data=PageData(
            items=[ProjectOut.model_validate(i) for i in items],
            total=total,
            page=paging.page,
            page_size=paging.page_size,
        )
    )


@router.get("/{project_id}", response_model=R[ProjectOut], summary="项目详情")
async def get_project(project_id: str, db: DBSession, user: CurrentUser):
    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")
    return R.ok(data=ProjectOut.model_validate(project))


@router.put("/{project_id}", response_model=R[ProjectOut], summary="更新项目")
async def update_project(
    project_id: str, body: ProjectUpdate, db: DBSession, user: CurrentUser
):
    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    updated = await project_crud.update(db, id=project_id, obj_in=body)
    return R.ok(data=ProjectOut.model_validate(updated))


@router.delete("/{project_id}", response_model=R, summary="删除项目")
async def delete_project(project_id: str, db: DBSession, user: CurrentUser):
    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    await project_crud.delete(db, id=project_id)
    return R.ok(message="删除成功")