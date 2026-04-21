"""Platform-level REST endpoints.

/health  — service health check (no auth required)
/stream  — SSE streaming chat (versioned chat handled by /api/v1/chat)

Product-versioned routes are served by app/api_routes/v1/.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.core.response import R
from app.dependencies import AppContainer, CurrentUser, DBSession, get_container

router = APIRouter(tags=["platform"])


@router.get("/health", summary="服务健康检查")
async def health(
    container: Annotated[AppContainer, Depends(get_container)],
) -> R:
    return R.ok(
        data={
            "status": "healthy",
            "env": container.settings.app_env,
            "app": container.settings.app_name,
        }
    )


@router.post("/stream", summary="SSE 流式对话")
async def stream(
    db: DBSession,
    user: CurrentUser,
    container: Annotated[AppContainer, Depends(get_container)],
    prompt: str = Form(..., description="用户消息"),
    file: UploadFile | None = File(default=None, description="可选附件"),
):
    return StreamingResponse(
        container.streamer.stream_chat(
            db=db,
            user=user,
            prompt=prompt,
            file=file,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
