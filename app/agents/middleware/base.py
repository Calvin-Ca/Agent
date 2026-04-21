"""Middleware base — protocol and chain for composable node wrappers.

Each middleware wraps a node function, adding behavior before/after execution.
The chain composes middlewares in order (first middleware is outermost).

Design:
    - Middleware.wrap(node_fn, next_fn) → returns a new callable
    - MiddlewareChain.wrap(node_fn) → applies all middlewares
    - Supports both sync and async node functions
"""

from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from typing import Callable

from app.agents.state import AgentState

# Type alias for node functions
NodeFunc = Callable[[AgentState], AgentState]


class Middleware(ABC):
    """Base class for all agent middleware.

    Subclasses implement ``wrap()`` which receives the original node function
    and a ``call_next`` callable. The middleware can:
    - Inspect / modify state before calling call_next
    - Inspect / modify the result after call_next returns
    - Handle exceptions from call_next
    - Skip call_next entirely (short-circuit)
    """

    @abstractmethod
    def wrap(self, node_fn: NodeFunc, call_next: NodeFunc) -> NodeFunc:
        """Wrap a node function with this middleware's behavior.

        Args:
            node_fn: The original (unwrapped) node function, for metadata access.
            call_next: The next function in the chain to call.

        Returns:
            A new callable with the same signature as the node function.
        """
        ...

    @property
    def name(self) -> str:
        """Middleware name for logging / metrics."""
        return self.__class__.__name__


class MiddlewareChain:
    """Ordered chain of middlewares applied to node functions.

    Middlewares are applied in order: first middleware is outermost (runs first/last).
    This matches the intuitive reading order:

        chain = MiddlewareChain([Logging, Metrics, Retry])
        # Execution: Logging → Metrics → Retry → actual_node → Retry → Metrics → Logging
    """

    def __init__(self, middlewares: list[Middleware] | None = None):
        self._middlewares: list[Middleware] = middlewares or []

    def add(self, middleware: Middleware) -> MiddlewareChain:
        """Add a middleware to the end of the chain. Returns self for fluent API."""
        self._middlewares.append(middleware)
        return self

    def wrap(self, node_fn: NodeFunc) -> NodeFunc:
        """Apply all middlewares to a node function, returning a wrapped callable."""
        wrapped = node_fn
        # Apply in reverse so first middleware is outermost
        for mw in reversed(self._middlewares):
            next_fn = wrapped
            wrapped = mw.wrap(node_fn, next_fn)
            functools.update_wrapper(wrapped, node_fn)
        return wrapped

    def apply_to_nodes(self, nodes: dict[str, NodeFunc]) -> dict[str, NodeFunc]:
        """Wrap all node functions in a dict. Useful for bulk graph setup.

        Args:
            nodes: Mapping of node_name → node_function.

        Returns:
            New dict with all node functions wrapped.
        """
        return {name: self.wrap(fn) for name, fn in nodes.items()}

    @property
    def middlewares(self) -> list[Middleware]:
        return list(self._middlewares)
