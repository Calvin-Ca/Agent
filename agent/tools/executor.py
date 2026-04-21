"""Async tool executor with timeout and retry support."""

from __future__ import annotations

import asyncio

from agent.tools.base import ToolOutput
from agent.tools.registry import ToolRegistry


class ToolExecutor:
    """Execute registered tools with timeout and retry semantics."""

    def __init__(self, registry: ToolRegistry, timeout_seconds: float = 15.0, retries: int = 1) -> None:
        self.registry = registry
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    async def execute(self, name: str, **kwargs) -> ToolOutput:
        tool = self.registry.get(name)
        last_error = ""
        for _ in range(self.retries + 1):
            try:
                return await asyncio.wait_for(tool.arun(**kwargs), timeout=self.timeout_seconds)
            except Exception as exc:
                last_error = str(exc)
        return ToolOutput(success=False, error=last_error)
