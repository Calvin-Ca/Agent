"""Request-scoped execution context for agent workflows."""

from __future__ import annotations

import time
import uuid
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CostAccumulator:
    """Track token usage and rough execution cost for a workflow run."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    estimated_cost_usd: float = 0.0

    def record_tokens(self, prompt: int = 0, completion: int = 0) -> None:
        self.prompt_tokens += prompt
        self.completion_tokens += completion
        self.llm_calls += 1

    def record_tool_call(self) -> None:
        self.tool_calls += 1

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }


@dataclass
class ExecutionContext:
    """Request-scoped metadata carried through agent execution."""

    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    tenant_id: str = ""
    user_id: str = ""
    trace_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    parent_span_id: str = ""
    timeout_seconds: float = 300.0
    metadata: dict[str, Any] = field(default_factory=dict)
    cost: CostAccumulator = field(default_factory=CostAccumulator)
    start_time: float = field(default_factory=time.time)

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.start_time

    @property
    def is_timed_out(self) -> bool:
        return self.elapsed_seconds > self.timeout_seconds

    def child_context(self, **overrides) -> ExecutionContext:
        """Create a child context that inherits tracing and time budget."""
        return ExecutionContext(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            trace_id=self.trace_id,
            parent_span_id=self.request_id,
            timeout_seconds=max(0, self.timeout_seconds - self.elapsed_seconds),
            metadata={**self.metadata, **overrides.pop("metadata", {})},
            **overrides,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "cost": self.cost.to_dict(),
        }


_context_var: ContextVar[ExecutionContext | None] = ContextVar("execution_context", default=None)


def set_context(ctx: ExecutionContext) -> Token:
    """Bind an execution context for the current scope."""
    return _context_var.set(ctx)


def reset_context(token: Token) -> None:
    """Reset the execution context for the current scope."""
    _context_var.reset(token)


def current_context() -> ExecutionContext:
    """Return the current context, creating a default one if needed."""
    ctx = _context_var.get(None)
    if ctx is None:
        return ExecutionContext()
    return ctx


__all__ = [
    "CostAccumulator",
    "ExecutionContext",
    "current_context",
    "reset_context",
    "set_context",
]
