"""Placeholder web search tool wrapper."""

from __future__ import annotations

from agent.tools.base import BaseTool, ToolOutput


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Search the web through an external provider."
    input_schema = {"type": "object", "properties": {"query": {"type": "string"}}}

    async def arun(self, **kwargs) -> ToolOutput:
        return ToolOutput(
            success=False,
            error="Web search is not configured in the local runtime yet.",
            metadata={"query": kwargs.get("query", "")},
        )
