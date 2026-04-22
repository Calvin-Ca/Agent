"""Shared state objects for chat turns and workflow execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from agent.input.preprocessor import UnifiedMessage


class WorkflowState(TypedDict, total=False):
    """State passed between workflow nodes."""

    task_type: Literal["report", "query", "unknown"]
    project_id: str
    user_id: str
    user_input: str
    week_start: str
    project_info: dict[str, Any]
    progress_records: list[dict[str, Any]]
    documents_text: list[str]
    image_descriptions: list[str]
    sql_results: list[dict[str, Any]]
    latest_video_info: dict[str, Any] | None
    report_draft: str
    report_title: str
    report_summary: str
    review_feedback: str
    query_answer: str
    current_step: str
    error: str
    retry_count: int
    done: bool
    request_id: str
    tenant_id: str
    session_id: str
    parent_request_id: str


@dataclass(slots=True)
class AgentState:
    """Per-turn execution state for the FastAPI chat loop."""

    user_id: str
    message: UnifiedMessage
    user_input: str
    intent: str
    params: dict[str, Any] = field(default_factory=dict)
    plan: list[Any] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    reflections: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    final_result: Any = None

    def add_trace(self, thought: str, action: str, observation: str) -> None:
        self.trace.append(
            {
                "thought": thought,
                "action": action,
                "observation": observation,
            }
        )
