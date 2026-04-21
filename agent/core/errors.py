"""Agent-specific exception hierarchy."""

from __future__ import annotations


class AgentError(Exception):
    """Base exception for all agent-related failures."""

    def __init__(
        self,
        message: str = "Agent execution error",
        *,
        node: str = "",
        recoverable: bool = False,
        details: dict | None = None,
    ):
        self.message = message
        self.node = node
        self.recoverable = recoverable
        self.details = details or {}
        super().__init__(message)


class PlanningError(AgentError):
    """Planner failed to validate or infer the request."""

    def __init__(self, message: str = "Planning failed", **kwargs):
        super().__init__(message, recoverable=False, **kwargs)


class DataCollectionError(AgentError):
    """Data collection node failed."""

    def __init__(self, message: str = "Data collection failed", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


class GenerationError(AgentError):
    """LLM generation failed."""

    def __init__(self, message: str = "LLM generation failed", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


class LLMTimeoutError(GenerationError):
    """LLM call exceeded the timeout budget."""

    def __init__(self, message: str = "LLM call timed out", **kwargs):
        super().__init__(message, **kwargs)


class LLMRateLimitError(GenerationError):
    """LLM backend returned a rate-limit response."""

    def __init__(self, message: str = "LLM rate limit exceeded", retry_after: float = 0, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, **kwargs)


class ReviewError(AgentError):
    """Report review or quality gate failed."""

    def __init__(self, message: str = "Review failed", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


class CheckpointError(AgentError):
    """Checkpoint save or restore failed."""

    def __init__(self, message: str = "Checkpoint operation failed", **kwargs):
        super().__init__(message, recoverable=False, **kwargs)


class ToolExecutionError(AgentError):
    """A registered tool failed during execution."""

    def __init__(self, message: str = "Tool execution failed", *, tool_name: str = "", **kwargs):
        self.tool_name = tool_name
        super().__init__(message, **kwargs)


class WorkflowTimeoutError(AgentError):
    """The overall workflow exceeded its timeout budget."""

    def __init__(self, message: str = "Workflow timed out", **kwargs):
        super().__init__(message, recoverable=False, **kwargs)


__all__ = [
    "AgentError",
    "CheckpointError",
    "DataCollectionError",
    "GenerationError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "PlanningError",
    "ReviewError",
    "ToolExecutionError",
    "WorkflowTimeoutError",
]
