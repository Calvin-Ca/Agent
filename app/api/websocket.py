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
        if (data.type === "token") console.log(data.content);
        if (data.type === "done") ws.close();
        if (data.type === "error") console.error(data.content);
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

router = APIRouter()


@router.websocket("/ws/report")
async def ws_report_stream(ws: WebSocket):
    """Stream report generation via WebSocket."""
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
            payload = decode_access_token(token) # token 解码后的字典（dict）
            user_id = payload.get("sub", "")
        except Exception:
            await _send(ws, "error", "token 无效或已过期")
            await ws.close()
            return

        # 3. Verify user exists
        factory = get_session_factory()     # 创建数据库会话
        async with factory() as db:
            user = await user_crud.get(db, id=user_id)
            if user is None:
                await _send(ws, "error", "用户不存在")
                await ws.close()
                return

        await _send(ws, "status", "开始生成周报...")  # 给前端发一条状态消息

        # 4. Run report generation in background thread
        from app.services.report_service import generate_report_sync

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, generate_report_sync, project_id, user_id, "",
        )

        if result["success"]:
            # Stream content in chunks (simulate token-by-token)
            content = result["content"]
            chunk_size = 50  # chars per chunk
            for i in range(0, len(content), chunk_size):
                chunk = content[i:i + chunk_size]
                await _send(ws, "token", chunk)
                await asyncio.sleep(0.02)  # small delay for streaming effect

            await _send(ws, "done", json.dumps({
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
        try:
            await ws.close()
        except Exception:
            pass


async def _send(ws: WebSocket, msg_type: str, content: str):
    """Send a typed message over WebSocket."""
    await ws.send_text(json.dumps({"type": msg_type, "content": content}))
