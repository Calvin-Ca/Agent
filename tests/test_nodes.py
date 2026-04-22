"""Unit tests for shared workflow nodes — helpers and routing."""

from __future__ import annotations

from agent.core.nodes import _extract_summary, route_after_data_collector, route_after_planner, route_after_reviewer


def test_extract_summary_with_heading():
    report = """# 项目周报

## 摘要
本周完成了基础开挖。
进度达到 35%。

## 本周工作
- 开挖基础
"""
    summary = _extract_summary(report)
    assert "基础开挖" in summary
    assert "35%" in summary


def test_extract_summary_fallback():
    report = """这是一份简短的周报
包含一些内容
没有摘要标题"""
    summary = _extract_summary(report)
    assert "简短的周报" in summary


def test_route_after_planner_error():
    state = {"error": "some error", "done": True}
    result = route_after_planner(state)
    assert result != "data_collector"


def test_route_after_planner_ok():
    state = {"error": ""}
    result = route_after_planner(state)
    assert result == "data_collector"


def test_route_after_data_collector_query():
    state = {"error": "", "task_type": "query"}
    result = route_after_data_collector(state)
    assert result == "progress_query"


def test_route_after_data_collector_report():
    state = {"error": "", "task_type": "report"}
    result = route_after_data_collector(state)
    assert result == "report_writer"


def test_route_after_reviewer_done():
    state = {"done": True}
    result = route_after_reviewer(state)
    # Should route to END
    assert result != "report_writer"


def test_route_after_reviewer_retry():
    state = {"done": False, "retry_count": 1}
    result = route_after_reviewer(state)
    assert result == "report_writer"
