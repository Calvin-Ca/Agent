"""Dependency injection container and service factories."""

from __future__ import annotations

from dataclasses import dataclass # 用来方便地定义“只装数据的类”
from functools import lru_cache   # 用来缓存函数结果，避免重复创建对象

# 把 app.api_routes.deps 里已经有的依赖，再从这里统一导出来。这样别的文件以后可以直接写：
# from app.dependencies import CurrentUser, DBSession
from app.api_routes.deps import (
    AdminUser,
    CurrentUser,
    DBSession,
    OptionalUser,
    get_current_user,
    get_db,
    get_optional_user,
    require_admin,
)
from app.services.chat_service import handle_chat
from agent.core.agent_loop import AgentLoop
from agent.infra.config import AppSettings, get_settings
from agent.output.streaming import ResponseStreamer


@dataclass(slots=True)
class AppContainer:
    """Lightweight service container for the application layer."""

    settings: AppSettings  # 项目配置
    agent_loop: AgentLoop
    streamer: ResponseStreamer # 流式输出器


def build_container() -> AppContainer:
    """Create the default service container."""
    settings = get_settings()
    agent_loop = AgentLoop(chat_handler=handle_chat)
    streamer = ResponseStreamer(agent_loop)
    return AppContainer(
        settings=settings,
        agent_loop=agent_loop,
        streamer=streamer,
    )


@lru_cache
def get_container() -> AppContainer:
    """Return the singleton service container."""
    return build_container()


__all__ = [
    "AdminUser",
    "AppContainer",
    "CurrentUser",
    "DBSession",
    "OptionalUser",
    "build_container",
    "get_container",
    "get_current_user",
    "get_db",
    "get_optional_user",
    "require_admin",
]
