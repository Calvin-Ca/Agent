"""Sandbox-friendly code interpreter placeholder."""

from __future__ import annotations

from agent.tools.base import BaseTool, ToolOutput


class CodeInterpreterTool(BaseTool):
    name = "code_interpreter"
    description = "Execute short Python snippets in a restricted context."
    input_schema = {"type": "object", "properties": {"code": {"type": "string"}}}

    async def arun(self, **kwargs) -> ToolOutput:
        code = kwargs.get("code", "")
        if "__" in code:
            return ToolOutput(success=False, error="Dunder access is not allowed in the sandbox.")
        scope: dict[str, object] = {}
        exec(code, {"__builtins__": {"len": len, "sum": sum, "min": min, "max": max}}, scope)
        return ToolOutput(success=True, data=scope)
