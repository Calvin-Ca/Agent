"""Semantic query business operations."""

from __future__ import annotations

import asyncio

from app.api_routes.deps import CurrentUser, DBSession
from app.core.exceptions import NotFoundError
from app.core.response import R
from app.crud.project import project_crud
from agent.infra.logger import run_in_executor_with_context
from app.schema_defs.chat import ChatResponse


def _chat_response(intent: str, message: str, data: dict | list | None = None):
    return R.ok(data=ChatResponse(intent=intent, message=message, data=data))


def _missing_project_response(intent: str):
    return _chat_response(
        intent,
        "未找到匹配的项目，请确认项目名称是否正确。可以说「查看我的项目」获取列表。",
    )


async def handle_query(
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
