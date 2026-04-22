"""Task decomposition and workflow planning helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, timedelta

from loguru import logger

from agent.core.state import AgentState, WorkflowState
from agent.infra.logger import log_node


@dataclass(slots=True)
class PlanStep:
    """Single planned step in the execution DAG."""

    name: str
    description: str
    depends_on: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExecutionPlan:
    """Ordered view of the per-turn plan."""

    steps: list[PlanStep]


class TaskPlanner:
    """Build a coarse execution plan from the recognized intent."""

    def build(self, state: AgentState) -> ExecutionPlan:
        if state.intent == "query":
            steps = [
                PlanStep("retrieve_context", "Fetch relevant project context"),
                PlanStep("reason", "Answer the user question", ["retrieve_context"]),
                PlanStep("format", "Shape the final response", ["reason"]),
            ]
        elif state.intent in {"upload_file", "generate_report"}:
            steps = [
                PlanStep("validate", "Validate request prerequisites"),
                PlanStep("dispatch", "Hand off work to the application service", ["validate"]),
                PlanStep("summarize", "Prepare user-facing confirmation", ["dispatch"]),
            ]
        else:
            steps = [
                PlanStep("understand", "Interpret the requested action"),
                PlanStep("execute", "Invoke the domain service", ["understand"]),
                PlanStep("respond", "Prepare the final response", ["execute"]),
            ]
        return ExecutionPlan(steps=steps)


class BasePlanner(ABC):
    """Abstract planner for workflow state validation and initialization."""

    @abstractmethod
    def plan(self, state: WorkflowState) -> WorkflowState:
        """Validate and prepare workflow state."""

    def _fail(self, state: WorkflowState, message: str) -> WorkflowState:
        return {**state, "error": message, "done": True}


class DefaultPlanner(BasePlanner):
    """Default planner implementation shared by query and report workflows."""

    report_keywords: tuple[str, ...] = (
        "周报",
        "报告",
        "生成",
        "撰写",
        "总结",
        "汇总",
        "月报",
        "写报告",
        "出报告",
        "编写报告",
        "生成报告",
    )
    query_keywords: tuple[str, ...] = (
        "怎么",
        "如何",
        "什么",
        "多少",
        "进展",
        "情况",
        "问题",
        "风险",
        "进度如何",
        "有没有",
        "是否",
        "为什么",
        "哪些",
    )

    def plan(self, state: WorkflowState) -> WorkflowState:
        project_id = state.get("project_id", "").strip()
        if not project_id:
            logger.error("[DefaultPlanner] missing project_id")
            return self._fail(state, "缺少项目ID")

        user_input = state.get("user_input", "")
        task_type = state.get("task_type", "unknown")
        if task_type not in {"report", "query"}:
            task_type = self._infer_task_type(user_input)

        if task_type == "query" and not user_input.strip():
            return self._fail(state, "查询模式需要提供问题内容")

        week_start = state.get("week_start", "")
        if task_type == "report":
            week_start = self._resolve_week_start(week_start)

        retry_count = state.get("retry_count") or 0
        return {
            **state,
            "task_type": task_type,
            "project_id": project_id,
            "week_start": week_start,
            "retry_count": retry_count,
            "current_step": "planner",
        }

    def _infer_task_type(self, user_input: str) -> str:
        if any(keyword in user_input for keyword in self.report_keywords):
            return "report"
        if any(keyword in user_input for keyword in self.query_keywords):
            return "query"
        return "report"

    def _resolve_week_start(self, week_start: str) -> str:
        if week_start:
            try:
                date.fromisoformat(week_start)
                return week_start
            except ValueError:
                logger.warning("[DefaultPlanner] invalid week_start '{}'", week_start)
        today = date.today()
        return (today - timedelta(days=today.weekday())).isoformat()


_default_planner = DefaultPlanner()


@log_node
def planner_node(state: WorkflowState) -> WorkflowState:
    """LangGraph-compatible planner node."""
    return _default_planner.plan(state)
