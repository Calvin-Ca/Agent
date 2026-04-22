"""Workflow implementations — query and report generation."""

from agent.workflows.query_workflow import QueryWorkflow, query_workflow
from agent.workflows.report_workflow import ReportWorkflow, report_workflow

__all__ = [
    "QueryWorkflow",
    "ReportWorkflow",
    "query_workflow",
    "report_workflow",
]
