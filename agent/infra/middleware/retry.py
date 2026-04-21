"""Retry middleware for recoverable agent errors."""

from __future__ import annotations

import functools
import time

from loguru import logger

from agent.core.errors import AgentError
from agent.core.state import WorkflowState
from agent.infra.middleware.base import Middleware, NodeFunc


class RetryMiddleware(Middleware):
    """Retry node execution on recoverable ``AgentError`` instances."""

    def __init__(
        self,
        max_retries: int = 2,
        base_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 30.0,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay

    def wrap(self, node_fn: NodeFunc, call_next: NodeFunc) -> NodeFunc:
        @functools.wraps(node_fn)
        def wrapper(state: WorkflowState) -> WorkflowState:
            node_name = node_fn.__name__
            last_error: Exception | None = None

            for attempt in range(1, self.max_retries + 2):
                try:
                    return call_next(state)
                except AgentError as exc:
                    last_error = exc
                    if not exc.recoverable or attempt > self.max_retries:
                        raise

                    delay = min(
                        self.base_delay * (self.backoff_factor ** (attempt - 1)),
                        self.max_delay,
                    )
                    logger.warning(
                        "[Retry:{}] attempt {}/{} failed: {} - retrying in {:.1f}s",
                        node_name,
                        attempt,
                        self.max_retries,
                        exc.message,
                        delay,
                    )
                    time.sleep(delay)
                except Exception:
                    raise

            raise last_error  # type: ignore[misc]

        return wrapper


__all__ = ["RetryMiddleware"]
