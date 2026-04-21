"""WebSocket endpoint for streaming report generation.

前端连接 `/ws/report` 这个 WebSocket 接口，发送项目 ID 和登录 token，
后端会把报告内容一段一段实时返回；生成完发 done，出错发 error。

WebSocket 很适合实时更新场景：AI 对话流式输出、聊天室、日志实时展示等。

Client connects, sends project_id + token, receives report tokens in real-time.

Usage (JS client):
    const ws = new WebSocket("ws://localhost:8000/ws/report");
    ws.onopen = () => ws.send(JSON.stringify({
        token: "Bearer xxx",
        project_id: "xxx",
    }));
    ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.type === "node_start") console.log("▶", data.node);
        if (data.type === "node_end")   console.log("✓", data.node, data.elapsed_ms + "ms");
        if (data.type === "token")      appendToReport(data.content);
        if (data.type === "done")       ws.close();
        if (data.type === "error")      console.error(data.content);
    };
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.security import decode_access_token
from app.crud.user import user_crud
from app.db.mysql import get_session_factory
from app.agents.callbacks.streaming import set_stream_queue, reset_stream_queue

router = APIRouter()

# Sentinel pushed to queue when generation is complete
_DONE_SENTINEL = object()


@router.websocket("/ws/report")
async def ws_report_stream(ws: WebSocket):
    """Stream report generation via WebSocket.

    Emits structured events:
        {"type": "status",     "content": "..."}
        {"type": "node_start", "node": "...", "task_type": "..."}
        {"type": "node_end",   "node": "...", "elapsed_ms": 123}
        {"type": "node_error", "node": "...", "error": "...", "elapsed_ms": 123}
        {"type": "token",      "content": "..."}
        {"type": "done",       "report_id": "...", "title": "..."}
        {"type": "error",      "content": "..."}
    """
    await ws.accept()

    try:
        # 1. Receive init message from frontend with auth token and project_id
        init_raw = await asyncio.wait_for(ws.receive_text(), timeout=10)
        init_data = json.loads(init_raw)

        token = init_data.get("token", "").removeprefix("Bearer ").strip()
        project_id = init_data.get("project_id", "")

        if not token or not project_id:
            await _send(ws, "error", "缺少 token 或 project_id")
            await ws.close()
            return

        # 2. Verify token
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub", "")
        except Exception:
            await _send(ws, "error", "token 无效或已过期")
            await ws.close()
            return

        # 3. Verify user exists
        factory = get_session_factory()
        async with factory() as db:
            user = await user_crud.get(db, id=user_id)
            if user is None:
                await _send(ws, "error", "用户不存在")
                await ws.close()
                return

        await _send(ws, "status", "开始生成周报...")

        # 4. Create stream queue and bind to context
        queue: asyncio.Queue = asyncio.Queue(maxsize=512)
        token_ctx = set_stream_queue(queue)

        from app.services.report_service import generate_report_sync
        from app.observability.logger import run_in_executor_with_context

        loop = asyncio.get_event_loop()

        # Run report generation in executor — node events flow into queue
        async def _run_generation():
            try:
                result = await run_in_executor_with_context(
                    loop, generate_report_sync, project_id, user_id, "",
                )
                return result
            finally:
                # Signal stream consumer that generation is done
                await queue.put(_DONE_SENTINEL)

        gen_task = asyncio.create_task(_run_generation())

        # 5. Forward stream events to WebSocket while generation runs
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=180)
            except asyncio.TimeoutError:
                await _send(ws, "error", "生成超时")
                gen_task.cancel()
                break

            if event is _DONE_SENTINEL:
                break

            # Forward event directly (it's already a typed dict)
            if isinstance(event, dict):
                await ws.send_text(json.dumps(event, ensure_ascii=False))

        # 6. Await generation result and send final done/error
        try:
            result = await gen_task
        except Exception as e:
            logger.error("Report generation failed: {}", e)
            await _send(ws, "error", str(e))
            return

        if result.get("success"):
            # Stream content in chunks for token-by-token effect
            content = result.get("content", "")
            chunk_size = 50
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                await _send(ws, "token", chunk)
                await asyncio.sleep(0.02)

            await ws.send_text(json.dumps({
                "type": "done",
                "report_id": result.get("report_id", ""),
                "title": result.get("title", ""),
            }))
        else:
            await _send(ws, "error", result.get("error", "生成失败"))

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except asyncio.TimeoutError:
        await _send(ws, "error", "连接超时")
    except Exception as e:
        logger.exception("WebSocket error: {}", e)
        try:
            await _send(ws, "error", str(e))
        except Exception:
            pass
    finally:
        if "token_ctx" in locals():
            reset_stream_queue(token_ctx)
        try:
            await ws.close()
        except Exception:
            pass


async def _send(ws: WebSocket, msg_type: str, content: str):
    """Send a typed message over WebSocket."""
    await ws.send_text(json.dumps({"type": msg_type, "content": content}))
