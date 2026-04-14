"""Base class and result type for all agent tools.

Every tool inherits from BaseTool and returns ToolResult.
This enables a unified registry-based invocation pattern.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    """Standardized return value from any tool execution."""

    success: bool
    data: Any = None
    error: str = ""
    metadata: dict = field(default_factory=dict)


class BaseTool(ABC):
    """Abstract base for all agent tools.

    Subclass and implement name / description / execute to create a new tool.
    Register via ``tool_registry.register(MyTool())``.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique tool name used for registry lookup, e.g. 'db.get_project_info'."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does."""

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Run the tool with the given parameters."""

    def __repr__(self) -> str:
        return f"<Tool:{self.name}>"
