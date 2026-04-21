"""DefaultPlanner — standard planner used by all built-in workflows.

Responsibilities
----------------
1. Validate that ``project_id`` is present.
2. Infer ``task_type`` from ``user_input`` when the caller passes "unknown"
   or omits the field.
3. Guard ``query`` mode: reject requests with an empty question.
4. Resolve ``week_start`` for ``report`` mode (validate supplied value or
   default to the current week's Monday).
5. Initialise ``retry_count`` to 0 when not already set.
"""

from __future__ import annotations

from datetime import date, timedelta

from loguru import logger

from app.agents.state import AgentState
from app.agents.planner.base import BasePlanner

# ── keyword sets for task-type inference ──────────────────────────────────

# Checked first — explicit report-creation intent
_REPORT_KEYWORDS: tuple[str, ...] = (
    "周报", "报告", "生成", "撰写", "总结", "汇总", "月报",
    "写报告", "出报告", "编写报告", "生成报告",
)

# Checked second — natural-language question intent
_QUERY_KEYWORDS: tuple[str, ...] = (
    "怎么", "如何", "什么", "多少", "进展", "情况", "问题",
    "风险", "进度如何", "有没有", "是否", "为什么", "哪些",
)


class DefaultPlanner(BasePlanner):
    """Default planner implementation shared by report and query workflows."""

    # Allow subclasses to override keyword sets without touching the logic
    report_keywords: tuple[str, ...] = _REPORT_KEYWORDS
    query_keywords: tuple[str, ...] = _QUERY_KEYWORDS

    # ── public interface ───────────────────────────────────────────────────

    def plan(self, state: AgentState) -> AgentState:
        """Validate inputs and initialise shared state fields."""

        # ── 1. project_id is mandatory ─────────────────────────────────────
        project_id = state.get("project_id", "").strip()
        if not project_id:
            logger.error("[DefaultPlanner] missing project_id")
            return self._fail(state, "缺少项目ID")

        user_input: str = state.get("user_input", "")
        task_type: str = state.get("task_type", "unknown")

        # ── 2. infer task_type when not explicitly set ─────────────────────
        if task_type not in ("report", "query"):
            task_type = self._infer_task_type(user_input)
            logger.info("[DefaultPlanner] inferred task_type='{}' from user_input", task_type)

        # ── 3. query mode requires a non-empty question ────────────────────
        if task_type == "query" and not user_input.strip():
            logger.error("[DefaultPlanner] query mode requires non-empty user_input")
            return self._fail(state, "查询模式需要提供问题内容")

        # ── 4. report mode: resolve week_start ────────────────────────────
        week_start: str = state.get("week_start", "")
        if task_type == "report":
            week_start = self._resolve_week_start(week_start)

        # ── 5. initialise retry_count ──────────────────────────────────────
        retry_count: int = state.get("retry_count") or 0

        logger.info(
            "[DefaultPlanner] task_type={} project_id={} week_start='{}' retry_count={}",
            task_type, project_id, week_start, retry_count,
        )

        return {
            **state,
            "task_type": task_type,
            "project_id": project_id,
            "week_start": week_start,
            "retry_count": retry_count,
            "current_step": "planner",
        }

    # ── private helpers ────────────────────────────────────────────────────

    def _infer_task_type(self, user_input: str) -> str:
        """Infer task_type from user_input keywords.

        Report keywords take priority over query keywords.
        Falls back to ``"report"`` when no keyword matches.
        """
        if any(kw in user_input for kw in self.report_keywords):
            return "report"
        if any(kw in user_input for kw in self.query_keywords):
            return "query"
        return "report"

    def _resolve_week_start(self, week_start: str) -> str:
        """Return a validated ISO week-start date.

        * If ``week_start`` is a valid ISO date string, return it unchanged.
        * If it is empty or invalid, default to the most recent Monday and
          log a warning for the invalid case.
        """
        if week_start:
            try:
                date.fromisoformat(week_start)
                return week_start
            except ValueError:
                logger.warning(
                    "[DefaultPlanner] invalid week_start='{}', defaulting to current Monday",
                    week_start,
                )

        monday = self._current_monday()
        if not week_start:
            logger.info("[DefaultPlanner] week_start not provided, defaulting to '{}'", monday)
        return monday

    @staticmethod
    def _current_monday() -> str:
        """Return the ISO date string for the most recent (or current) Monday."""
        today = date.today()
        return (today - timedelta(days=today.weekday())).isoformat()
