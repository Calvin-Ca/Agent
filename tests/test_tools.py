from __future__ import annotations

import pytest

from agent.tools.base import BaseTool, ToolOutput
from agent.tools.executor import ToolExecutor
from agent.tools.registry import ToolRegistry


class EchoTool(BaseTool):
    name = "echo"
    description = "echo"

    async def arun(self, **kwargs) -> ToolOutput:
        return ToolOutput(success=True, data=kwargs.get("value"))


@pytest.mark.asyncio
async def test_registry_and_executor_roundtrip():
    registry = ToolRegistry()
    registry.register(EchoTool())
    executor = ToolExecutor(registry)

    result = await executor.execute("echo", value="hello")

    assert result.success is True
    assert result.data == "hello"
