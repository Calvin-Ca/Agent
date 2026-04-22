"""Tests for tool registry, executor, and auto-discovery."""

from __future__ import annotations

import pytest

from agent.tools.base import BaseTool, ToolOutput
from agent.tools.executor import ToolExecutor
from agent.tools.registry import ToolRegistry, auto_discover_tools, tool_registry


class EchoTool(BaseTool):
    name = "echo"
    description = "echo"

    async def arun(self, **kwargs) -> ToolOutput:
        return ToolOutput(success=True, data=kwargs.get("value"))


class FailTool(BaseTool):
    name = "fail"
    description = "always fails"

    async def arun(self, **kwargs) -> ToolOutput:
        return ToolOutput(success=False, error="intentional failure")


@pytest.mark.asyncio
async def test_registry_and_executor_roundtrip():
    registry = ToolRegistry()
    registry.register(EchoTool())
    executor = ToolExecutor(registry)

    result = await executor.execute("echo", value="hello")

    assert result.success is True
    assert result.data == "hello"


def test_registry_list():
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(FailTool())

    names = registry.list()
    assert "echo" in names
    assert "fail" in names
    assert names == sorted(names)


def test_registry_has():
    registry = ToolRegistry()
    registry.register(EchoTool())
    assert registry.has("echo") is True
    assert registry.has("nonexistent") is False


def test_registry_unregister():
    registry = ToolRegistry()
    registry.register(EchoTool())
    assert registry.has("echo") is True

    registry.unregister("echo")
    assert registry.has("echo") is False


def test_registry_get_missing():
    registry = ToolRegistry()
    with pytest.raises(KeyError, match="Tool 'missing'"):
        registry.get("missing")


def test_registry_bulk_register():
    registry = ToolRegistry()
    registry.bulk_register([EchoTool(), FailTool()])
    assert len(registry.list()) == 2


def test_registry_list_tools_metadata():
    registry = ToolRegistry()
    registry.register(EchoTool())
    tools = registry.list_tools()
    assert len(tools) == 1
    assert tools[0]["name"] == "echo"
    assert tools[0]["description"] == "echo"


@pytest.mark.asyncio
async def test_executor_failure():
    registry = ToolRegistry()
    registry.register(FailTool())
    executor = ToolExecutor(registry)

    result = await executor.execute("fail")
    assert result.success is False
    assert "intentional" in result.error


@pytest.mark.asyncio
async def test_executor_missing_tool():
    registry = ToolRegistry()
    executor = ToolExecutor(registry)

    with pytest.raises(KeyError):
        await executor.execute("nonexistent")


def test_auto_discover_tools_idempotent():
    """auto_discover_tools should be safe to call multiple times."""
    initial_count = len(tool_registry.list())
    auto_discover_tools()
    count_after_first = len(tool_registry.list())
    auto_discover_tools()
    count_after_second = len(tool_registry.list())

    assert count_after_first >= initial_count
    assert count_after_second == count_after_first
