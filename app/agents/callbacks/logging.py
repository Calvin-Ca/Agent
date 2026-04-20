"""Logging callback — timing decorator for LangGraph node functions.

Wraps each node to log:
- Node entry with key input parameters
- Node exit with elapsed time
- Error details if the node fails
"""

from __future__ import annotations

import time
import functools
from typing import Callable

from loguru import logger

from app.agents.state import AgentState


def log_node(func: Callable[[AgentState], AgentState]) -> Callable[[AgentState], AgentState]:
    """Decorator that logs node entry, exit, timing, and errors."""

    @functools.wraps(func)
    def wrapper(state: AgentState) -> AgentState:
        node_name = func.__name__
        project_id = state.get("project_id", "-")
        task_type = state.get("task_type", "-")
        step = state.get("current_step", "-")

        logger.info(
            "[Node:{}] START | project={} task={} prev_step={}",
            node_name, project_id, task_type, step,
        )

        start = time.perf_counter()
        try:
            result = func(state)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(
                "[Node:{}] FAILED after {:.0f}ms | error={}",
                node_name, elapsed_ms, e,
            )
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        new_step = result.get("current_step", "-")
        error = result.get("error", "")
        done = result.get("done", False)

        if error:
            logger.warning(
                "[Node:{}] DONE {:.0f}ms | error={} done={}",
                node_name, elapsed_ms, error, done,
            )
        else:
            logger.info(
                "[Node:{}] DONE {:.0f}ms | step={} done={}",
                node_name, elapsed_ms, new_step, done,
            )

        return result

    return wrapper
