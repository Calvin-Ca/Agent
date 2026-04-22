"""Backward-compatible re-exports — canonical module is agent.workflows."""

from agent.workflows import QueryWorkflow, ReportWorkflow, query_workflow, report_workflow  # noqa: F401

__all__ = [
    "QueryWorkflow",
    "ReportWorkflow",
    "query_workflow",
    "report_workflow",
]
