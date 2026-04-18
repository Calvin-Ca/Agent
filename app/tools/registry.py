"""Central tool registry — register, look up, and execute tools by name.

Usage:
    from app.tools.registry import tool_registry

    # Execute a tool by name
    result = tool_registry.execute("db.get_project_info", project_id="xxx")

    # List all registered tools
    tool_registry.list_tools()
"""

from __future__ import annotations

import threading

from loguru import logger

from app.tools.base import BaseTool, ToolResult


class ToolRegistry:
    """Central registry for all available tools. Singleton."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._lock = threading.Lock()

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance. Overwrites if name exists."""
        with self._lock:
            self._tools[tool.name] = tool
            logger.info("Registered tool: {}", tool.name)

    def unregister(self, name: str) -> None:
        """Remove a tool by name."""
        with self._lock:
            if name in self._tools:
                del self._tools[name]
                logger.info("Unregistered tool: {}", name)

    def get(self, name: str) -> BaseTool:
        """Get a tool by name. Raises KeyError if not found."""
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"Tool '{name}' not registered. Available: {list(self._tools.keys())}")
        return tool

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def list_tools(self) -> list[dict]:
        """Return metadata for all registered tools."""
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    def execute(self, name: str, **kwargs) -> ToolResult:
        """Look up a tool and execute it."""
        return self.get(name).execute(**kwargs)


# Singleton
tool_registry = ToolRegistry()


def auto_discover_tools() -> None:
    """Register all built-in tools. Called at app startup."""
    from app.tools.builtin.sql_query import (
        GetProjectInfoTool,
        GetRecentProgressTool,
        GetRecentReportsTool,
        GetDocumentListTool,
    )
    from app.tools.builtin.vector_search import VectorSearchTool, MultiQuerySearchTool
    from app.tools.builtin.file_ops import ExportDocxTool, ExportMarkdownTool
    from app.tools.builtin.minio_query import GetLatestVideoTool

    builtin_tools = [
        GetProjectInfoTool(),
        GetRecentProgressTool(),
        GetRecentReportsTool(),
        GetDocumentListTool(),
        VectorSearchTool(),
        MultiQuerySearchTool(),
        ExportDocxTool(),
        ExportMarkdownTool(),
        GetLatestVideoTool(),
    ]

    for tool in builtin_tools:
        tool_registry.register(tool)

    logger.info("Tool registry: {} tools registered", len(builtin_tools))
