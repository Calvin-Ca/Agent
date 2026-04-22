"""Project-related business operations."""

from __future__ import annotations

from app.api_routes.deps import CurrentUser, DBSession
from app.core.exceptions import NotFoundError
from app.core.response import R
from app.crud.project import project_crud
from app.schema_defs.chat import ChatResponse
from app.schema_defs.project import ProjectCreate, ProjectOut, ProjectUpdate


def _chat_response(intent: str, message: str, data: dict | list | None = None):
    return R.ok(data=ChatResponse(intent=intent, message=message, data=data))


def _missing_project_response(intent: str):
    return _chat_response(
        intent,
        "未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
    )


async def handle_create_project(db: DBSession, user: CurrentUser, params: dict):
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


async def handle_list_projects(db: DBSession, user: CurrentUser):
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


async def handle_update_project(
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


async def handle_delete_project(db: DBSession, user: CurrentUser, project_id: str | None):
    if not project_id:
        return _missing_project_response("delete_project")

    project = await project_crud.get(db, id=project_id)
    if project is None or project.owner_id != user.id:
        raise NotFoundError("项目不存在")

    await project_crud.delete(db, id=project_id)
    return _chat_response("delete_project", f"项目「{project.name}」已删除。")
