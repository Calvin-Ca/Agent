"""Product-facing chat endpoint."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.dependencies import AppContainer, CurrentUser, DBSession, get_container

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", summary="智能对话")
async def chat(
    db: DBSession,
    user: CurrentUser,
    container: Annotated[AppContainer, Depends(get_container)],
    prompt: str = Form(..., description="用户提示词"),
    file: UploadFile | None = File(default=None, description="上传文件（可选）"),
):
    return await container.agent_loop.handle_chat(
        db=db,
        user=user,
        prompt=prompt,
        file=file,
    )
