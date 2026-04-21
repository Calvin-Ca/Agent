"""Generic REST API caller tool."""

from __future__ import annotations

import httpx

from agent.tools.base import BaseTool, ToolOutput


class APICallerTool(BaseTool):
    name = "api_caller"
    description = "Call REST APIs with a configurable method and payload."
    input_schema = {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "method": {"type": "string"},
            "json": {"type": "object"},
        },
        "required": ["url"],
    }

    async def arun(self, **kwargs) -> ToolOutput:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.request(
                method=kwargs.get("method", "GET"),
                url=kwargs["url"],
                json=kwargs.get("json"),
                headers=kwargs.get("headers"),
            )
        return ToolOutput(
            success=response.is_success,
            data={"status_code": response.status_code, "body": response.text},
        )
