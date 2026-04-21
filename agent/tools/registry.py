"""Central registry for built-in and custom tools."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterable

from loguru import logger

from agent.tools.base import BaseTool, ToolOutput


class ToolRegistry:
    """Register, resolve, and execute tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._lock = threading.Lock()

    def register(self, tool: BaseTool) -> None:
        with self._lock:
            self._tools[tool.name] = tool
            logger.info("Registered tool: {}", tool.name)

    def bulk_register(self, tools: Iterable[BaseTool]) -> None:
        for tool in tools:
            self.register(tool)

    def unregister(self, name: str) -> None:
        with self._lock:
            self._tools.pop(name, None)

    def get(self, name: str) -> BaseTool:
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not registered. Available: {list(self._tools.keys())}")
        return tool

    def has(self, name: str) -> bool:
        return name in self._tools

    def list(self) -> list[str]:
        return sorted(self._tools)

    def list_tools(self) -> list[dict[str, str]]:
        return [{"name": tool.name, "description": tool.description} for tool in self._tools.values()]

    def execute(self, name: str, **kwargs) -> ToolOutput:
        tool = self.get(name)
        if type(tool).execute is not BaseTool.execute:
            return tool.execute(**kwargs)
        return asyncio.run(tool.arun(**kwargs))


tool_registry = ToolRegistry()


def auto_discover_tools() -> None:
    """Register the built-in tools used by the agent workflows."""
    from agent.tools.builtin.db_query import (
        GetDocumentListTool,
        GetProjectInfoTool,
        GetRecentProgressTool,
        GetRecentReportsTool,
        MultiQuerySearchTool,
        VectorSearchTool,
    )
    from agent.tools.builtin.file_manager import ExportDocxTool, ExportMarkdownTool, GetLatestVideoTool

    for tool in (
        GetProjectInfoTool(),
        GetRecentProgressTool(),
        GetRecentReportsTool(),
        GetDocumentListTool(),
        VectorSearchTool(),
        MultiQuerySearchTool(),
        ExportDocxTool(),
        ExportMarkdownTool(),
        GetLatestVideoTool(),
    ):
        if not tool_registry.has(tool.name):
            tool_registry.register(tool)
