"""Product-facing chat endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Form, UploadFile, File

from app.api.deps import CurrentUser, DBSession
from app.services.chat_service import handle_chat

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", summary="智能对话")
async def chat(
    db: DBSession,
    user: CurrentUser,
    prompt: str = Form(..., description="用户提示词"),
    file: UploadFile | None = File(default=None, description="上传文件（可选）"),
):
    return await handle_chat(db=db, user=user, prompt=prompt, file=file)
