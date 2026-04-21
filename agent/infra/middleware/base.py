"""Middleware protocol and chain utilities for workflow nodes."""

from __future__ import annotations

import functools
from abc import ABC, abstractmethod
from typing import Callable

from agent.core.state import WorkflowState

NodeFunc = Callable[[WorkflowState], WorkflowState]


class Middleware(ABC):
    """Base class for workflow middleware."""

    @abstractmethod
    def wrap(self, node_fn: NodeFunc, call_next: NodeFunc) -> NodeFunc:
        """Wrap a node function with this middleware."""

    @property
    def name(self) -> str:
        return self.__class__.__name__


class MiddlewareChain:
    """Apply middleware in declaration order around a node function."""

    def __init__(self, middlewares: list[Middleware] | None = None) -> None:
        self._middlewares: list[Middleware] = middlewares or []

    def add(self, middleware: Middleware) -> MiddlewareChain:
        self._middlewares.append(middleware)
        return self

    def wrap(self, node_fn: NodeFunc) -> NodeFunc:
        wrapped = node_fn
        for middleware in reversed(self._middlewares):
            next_fn = wrapped
            wrapped = middleware.wrap(node_fn, next_fn)
            functools.update_wrapper(wrapped, node_fn)
        return wrapped

    def apply_to_nodes(self, nodes: dict[str, NodeFunc]) -> dict[str, NodeFunc]:
        return {name: self.wrap(fn) for name, fn in nodes.items()}

    @property
    def middlewares(self) -> list[Middleware]:
        return list(self._middlewares)


__all__ = ["Middleware", "MiddlewareChain", "NodeFunc"]
