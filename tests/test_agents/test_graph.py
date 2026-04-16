"""Unit tests for agent nodes and graph routing."""

from __future__ import annotations

from app.agents.state import AgentState
from app.agents.planner.default_planner import planner_node


class TestPlanner:

    def _base_state(self, **overrides) -> AgentState:
        state: AgentState = {
            "task_type": "unknown",
            "project_id": "test_proj_001",
            "user_id": "test_user",
            "user_input": "",
            "week_start": "",
            "project_info": {},
            "progress_records": [],
            "documents_text": [],
            "image_descriptions": [],
            "sql_results": [],
            "report_draft": "",
            "report_title": "",
            "report_summary": "",
            "review_feedback": "",
            "query_answer": "",
            "current_step": "",
            "error": "",
            "retry_count": 0,
            "done": False,
        }
        state.update(overrides)
        return state

    def test_route_report_explicit(self):
        state = self._base_state(task_type="report")
        result = planner_node(state)
        assert result["task_type"] == "report"
        assert result["error"] == ""

    def test_route_query_explicit(self):
        state = self._base_state(task_type="query", user_input="进度如何？")
        result = planner_node(state)
        assert result["task_type"] == "query"

    def test_infer_report_from_input(self):
        state = self._base_state(task_type="unknown", user_input="帮我生成周报")
        result = planner_node(state)
        assert result["task_type"] == "report"

    def test_infer_query_from_input(self):
        state = self._base_state(task_type="unknown", user_input="目前进度如何？")
        result = planner_node(state)
        assert result["task_type"] == "query"

    def test_missing_project_id(self):
        state = self._base_state(project_id="")
        result = planner_node(state)
        assert result["error"] != ""
        assert result["done"] is True

    def test_default_to_report(self):
        state = self._base_state(task_type="unknown", user_input="")
        result = planner_node(state)
        assert result["task_type"] == "report"


class TestPromptTemplates:

    def test_build_report_prompt(self):
        from app.agents.prompts.templates import build_report_prompt

        prompt = build_report_prompt(
            project_info={"name": "测试项目", "code": "TST-001", "description": "测试"},
            progress_records=[
                {"date": "2026-04-07", "progress": 65, "milestone": "基础完成",
                 "description": "本周完成基础", "blockers": "", "next_steps": "开始主体"},
            ],
            documents_text=["文档片段内容"],
            prev_reports=[],
            week_start="2026-04-07",
            week_end="2026-04-13",
        )
        assert "测试项目" in prompt
        assert "TST-001" in prompt
        assert "65%" in prompt
        assert "2026-04-07" in prompt

    def test_build_query_prompt(self):
        from app.agents.prompts.templates import build_query_prompt

        prompt = build_query_prompt(
            question="目前进度如何？",
            project_info={"name": "测试项目", "code": "TST", "description": ""},
            progress_records=[
                {"date": "2026-04-07", "progress": 80, "description": "主体完成80%"},
            ],
            documents_text=["相关内容"],
        )
        assert "目前进度如何" in prompt
        assert "80%" in prompt

    def test_empty_data_does_not_crash(self):
        from app.agents.prompts.templates import build_report_prompt, build_query_prompt

        # Should not raise with empty data
        build_report_prompt({}, [], [], [], "2026-04-07", "2026-04-13")
        build_query_prompt("问题", {}, [], [])