"""Base tool abstractions for the refactored tool layer."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ToolOutput:
    """Standardized result from any tool invocation."""

    success: bool
    data: Any = None
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


ToolResult = ToolOutput


class BaseTool:
    """Unified tool contract supporting sync and async implementations."""

    name: str = ""
    description: str = ""
    input_schema: dict[str, Any] = {}

    def execute(self, **kwargs) -> ToolOutput:
        """Execute the tool synchronously."""
        raise NotImplementedError(f"{self.__class__.__name__} does not implement execute()")

    async def arun(self, **kwargs) -> ToolOutput:
        """Execute the tool asynchronously."""
        if type(self).execute is BaseTool.execute:
            raise NotImplementedError(f"{self.__class__.__name__} does not implement arun()")
        return await asyncio.to_thread(self.execute, **kwargs)
