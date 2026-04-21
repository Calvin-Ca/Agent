"""Retry middleware — automatic retry with exponential backoff for recoverable errors.

Only retries errors marked as ``recoverable=True`` in the AgentError hierarchy.
Non-recoverable errors propagate immediately.

Usage:
    chain = MiddlewareChain([
        RetryMiddleware(max_retries=2, base_delay=1.0, backoff_factor=2.0),
        ...
    ])
"""

from __future__ import annotations

import functools
import time

from loguru import logger

from app.agents.state import AgentState
from app.agents.errors import AgentError
from app.agents.middleware.base import Middleware, NodeFunc


class RetryMiddleware(Middleware):
    """Retries node execution on recoverable AgentErrors with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts (default: 2).
        base_delay: Initial delay in seconds before first retry (default: 1.0).
        backoff_factor: Multiplier for delay on each subsequent retry (default: 2.0).
        max_delay: Maximum delay cap in seconds (default: 30.0).
    """

    def __init__(
        self,
        max_retries: int = 2,
        base_delay: float = 1.0,
        backoff_factor: float = 2.0,
        max_delay: float = 30.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay

    def wrap(self, node_fn: NodeFunc, call_next: NodeFunc) -> NodeFunc:
        @functools.wraps(node_fn)
        def wrapper(state: AgentState) -> AgentState:
            node_name = node_fn.__name__
            last_error: Exception | None = None

            for attempt in range(1, self.max_retries + 2):  # +2: 1 initial + max_retries
                try:
                    return call_next(state)
                except AgentError as e:
                    last_error = e
                    if not e.recoverable or attempt > self.max_retries:
                        raise

                    delay = min(
                        self.base_delay * (self.backoff_factor ** (attempt - 1)),
                        self.max_delay,
                    )
                    logger.warning(
                        "[Retry:{}] attempt {}/{} failed: {} — retrying in {:.1f}s",
                        node_name, attempt, self.max_retries, e.message, delay,
                    )
                    time.sleep(delay)
                except Exception:
                    # Non-AgentError exceptions are not retried
                    raise

            # Should not reach here, but just in case
            raise last_error  # type: ignore[misc]

        return wrapper
