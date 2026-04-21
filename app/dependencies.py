"""Dependency injection container and service factories."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from app.api_routes.deps import (  # Re-export legacy FastAPI dependencies.
    AdminUser,
    CurrentUser,
    DBSession,
    OptionalUser,
    Paging,
    PagingParams,
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

    settings: AppSettings
    agent_loop: AgentLoop
    streamer: ResponseStreamer


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
    "Paging",
    "PagingParams",
    "build_container",
    "get_container",
    "get_current_user",
    "get_db",
    "get_optional_user",
    "require_admin",
]
