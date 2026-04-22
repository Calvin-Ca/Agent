"""Unified streaming agent endpoint.

All business interactions go through this single SSE endpoint.
The agent handles intent recognition, planning, and execution internally.

SSE event protocol:
    event: connected   — session acknowledged
    event: thinking    — agent processing stage indicator
    event: intent      — recognized intent, params, and execution plan
    event: node_start  — workflow node begins execution
    event: node_end    — workflow node completed
    event: token       — incremental content chunk (for streaming LLM output)
    event: result      — final structured response
    event: error       — error with reflections
    event: done        — stream complete
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse

from app.dependencies import AppContainer, CurrentUser, DBSession, get_container

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/stream", summary="Agent 流式对话")
async def agent_stream(
    db: DBSession,
    user: CurrentUser,
    container: Annotated[AppContainer, Depends(get_container)],     # 表示这个参数最终拿到的值，类型是 AppContainer。Depends(get_container)表示这个参数不是让前端传进来的，而是让 FastAPI 自动调用 get_container() 来提供
    prompt: str = Form(..., description="用户消息"),
    file: UploadFile | None = File(default=None, description="可选附件"),
):
    """Single entry point for all business operations via SSE streaming.

    The agent recognises the user's intent from natural language, plans
    execution steps, and streams progress events back to the client in
    real time.
    """
    conversation_id = uuid.uuid4().hex

    return StreamingResponse(           # StreamingResponse 接受一个生成器（yield）作为响应体返回
        container.streamer.stream_chat(  
            db=db,
            user=user,
            prompt=prompt,
            file=file,
            conversation_id=conversation_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Conversation-Id": conversation_id,
        },
    )
