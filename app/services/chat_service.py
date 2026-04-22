"""Chat service — thin intent dispatcher.

All business logic lives in dedicated service modules; this file only routes
intents and resolves project names.
"""

from __future__ import annotations

import time

from fastapi import UploadFile
from loguru import logger

from app.api_routes.deps import CurrentUser, DBSession
from app.core.exceptions import BizError, NotFoundError
from app.core.response import R
from app.crud.project import project_crud
from agent.core.state import AgentState
from app.schema_defs.chat import ChatResponse

from app.services.project_service import (
    handle_create_project,
    handle_delete_project,
    handle_list_projects,
    handle_update_project,
)
from app.services.progress_service import handle_list_progress, handle_record_progress
from app.services.report_service import (
    handle_export_report,
    handle_generate_report,
    handle_get_report,
    handle_list_reports,
)
from app.services.document_service import handle_upload_file
from app.services.query_service import handle_query

_NO_PROJECT_INTENTS = {
    "create_project",
    "list_projects",
    "list_reports",
    "get_report",
    "export_report",
}


def _chat_response(intent: str, message: str, data: dict | list | None = None):
    return R.ok(data=ChatResponse(intent=intent, message=message, data=data))


async def handle_chat(
    db: DBSession,
    user: CurrentUser,
    state: AgentState,
    file: UploadFile | None = None,
):
    """Dispatch to the matching product action using the pre-resolved AgentState."""
    started_at = time.perf_counter()
    intent = state.intent
    params = state.params
    has_file = file is not None and bool(file.filename)
    logger.info(
        "[Chat] 分派请求 | user={} intent={} params={} has_file={}",
        user.id,
        intent,
        params,
        bool(has_file),
    )

    resolved_project_id = None
    if intent not in _NO_PROJECT_INTENTS:
        project_name = params.get("project_name", "")
        if project_name:
            resolved_project_id = await _resolve_project_id(db, user.id, project_name)

    try:
        if intent == "create_project":
            result = await handle_create_project(db, user, params)
        elif intent == "list_projects":
            result = await handle_list_projects(db, user)
        elif intent == "update_project":
            result = await handle_update_project(db, user, resolved_project_id, params)
        elif intent == "delete_project":
            result = await handle_delete_project(db, user, resolved_project_id)
        elif intent == "record_progress":
            result = await handle_record_progress(db, user, resolved_project_id, params)
        elif intent == "list_progress":
            result = await handle_list_progress(db, user, resolved_project_id)
        elif intent == "generate_report":
            result = await handle_generate_report(user, db, resolved_project_id, params)
        elif intent == "list_reports":
            filter_project_id = None
            project_name = params.get("project_name", "")
            if project_name:
                filter_project_id = await _resolve_project_id(db, user.id, project_name)
            result = await handle_list_reports(db, user, filter_project_id)
        elif intent == "get_report":
            result = await handle_get_report(db, user, params)
        elif intent == "export_report":
            result = await handle_export_report(db, user, params)
        elif intent == "upload_file":
            if not has_file:
                result = _chat_response(intent, "请上传文件后重试。")
            else:
                result = await handle_upload_file(db, user, resolved_project_id, file)
        else:
            result = await handle_query(db, user, resolved_project_id, params, state.user_input)
    except NotFoundError as exc:
        result = _chat_response(intent, str(exc))
    except BizError as exc:
        result = _chat_response(intent, exc.message)

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    logger.info(
        "[Chat] 完成 | user={} intent={} elapsed={:.0f}ms",
        user.id,
        intent,
        elapsed_ms,
    )
    return result


async def _resolve_project_id(
    db: DBSession,
    owner_id: str,
    project_name: str,
) -> str | None:
    """Resolve a project name to the best-matching project id."""
    matches = await project_crud.get_by_name(db, name=project_name, owner_id=owner_id)

    if not matches:
        logger.info("[Resolve] 未找到项目 | name='{}' owner={}", project_name, owner_id)
        return None

    if len(matches) == 1:
        project = matches[0]
        logger.info("[Resolve] 匹配项目 | name='{}' → id={} ({})", project_name, project.id, project.name)
        return project.id

    for project in matches:
        if project.name == project_name:
            logger.info("[Resolve] 精确匹配 | name='{}' → id={}", project_name, project.id)
            return project.id

    project = matches[0]
    logger.info(
        "[Resolve] 模糊匹配({}个候选) | name='{}' → id={} ({})",
        len(matches),
        project_name,
        project.id,
        project.name,
    )
    return project.id
