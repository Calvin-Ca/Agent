"""Default planner — determines task type and routes the workflow."""

from __future__ import annotations

from loguru import logger

from app.agents.state import AgentState
from app.agents.callbacks.logging import log_node


@log_node
def planner_node(state: AgentState) -> AgentState:
    """Route based on task_type. Validates required fields."""
    task_type = state.get("task_type", "unknown")
    project_id = state.get("project_id", "")

    if not project_id:
        logger.error("Planner: missing project_id")
        return {**state, "error": "缺少项目ID", "done": True}

    if task_type not in ("report", "query"):  # 如果传进来的 task_type 不是合法值，就尝试根据 user_input 自动推断
        # Try to infer from user_input
        user_input = state.get("user_input", "")
        if any(kw in user_input for kw in ("周报", "报告", "生成", "撰写")):
            task_type = "report"
        elif user_input:
            task_type = "query"
        else:
            task_type = "report"  # default

    logger.info("Planner: task_type={}, project_id={}", task_type, project_id)
    return {**state, "task_type": task_type, "current_step": "planner"}
