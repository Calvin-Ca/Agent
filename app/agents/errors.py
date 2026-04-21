"""Agent-specific exception hierarchy.

Provides fine-grained error types for the agent pipeline so that
middleware, graphs, and API layers can handle failures precisely.

Exception tree:
    AgentError (base)
    ├── PlanningError          — planner validation / inference failure
    ├── DataCollectionError    — tool or DB fetch failure
    ├── GenerationError        — LLM generation failure
    │   ├── LLMTimeoutError    — LLM call exceeded timeout
    │   └── LLMRateLimitError  — LLM backend returned 429
    ├── ReviewError            — review / quality gate failure
    ├── CheckpointError        — checkpoint save / load failure
    ├── ToolExecutionError     — tool execution failure
    └── WorkflowTimeoutError   — overall workflow exceeded timeout

Usage:
    from app.agents.errors import GenerationError, LLMTimeoutError

    try:
        result = llm_generate(prompt)
    except LLMTimeoutError:
        # fallback to simpler model
        ...
"""

from __future__ import annotations


class AgentError(Exception):
    """Base exception for all agent-related errors.

    Attributes:
        message: Human-readable error description.
        node: The node name where the error occurred (if applicable).
        recoverable: Whether the caller should attempt retry / fallback.
        details: Arbitrary context dict for debugging.
    """

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
    """Planner failed to validate inputs or infer task type."""

    def __init__(self, message: str = "Planning failed", **kwargs):
        super().__init__(message, recoverable=False, **kwargs)


class DataCollectionError(AgentError):
    """Data collection node failed (DB / vector search / tool call)."""

    def __init__(self, message: str = "Data collection failed", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


class GenerationError(AgentError):
    """LLM generation failed."""

    def __init__(self, message: str = "LLM generation failed", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


class LLMTimeoutError(GenerationError):
    """LLM call exceeded the configured timeout."""

    def __init__(self, message: str = "LLM call timed out", **kwargs):
        super().__init__(message, **kwargs)


class LLMRateLimitError(GenerationError):
    """LLM backend returned HTTP 429 — too many requests."""

    def __init__(self, message: str = "LLM rate limit exceeded", retry_after: float = 0, **kwargs):
        self.retry_after = retry_after
        super().__init__(message, **kwargs)


class ReviewError(AgentError):
    """Report review / quality gate failure."""

    def __init__(self, message: str = "Review failed", **kwargs):
        super().__init__(message, recoverable=True, **kwargs)


class CheckpointError(AgentError):
    """Checkpoint save or load failure."""

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
