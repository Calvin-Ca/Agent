"""Agent state schema — defines the data flowing through the LangGraph workflow.

Every node reads from and writes to this state dict.
"""

from __future__ import annotations

from typing import TypedDict, Literal


class AgentState(TypedDict, total=False):
    """State passed between LangGraph nodes.

    Fields:
        # ── Input ────────────────────────────────────────────
        task_type: What the user wants — "report" | "query" | "unknown"
        project_id: Target project ID
        user_id: Who triggered this
        user_input: Raw user message (for query mode)
        week_start: Report week start date (ISO format string)

        # ── Collected Data ───────────────────────────────────
        project_info: Project metadata from MySQL
        progress_records: Recent progress snapshots
        documents_text: Retrieved document chunks from Milvus
        image_descriptions: VLM descriptions of site photos
        sql_results: Results from structured DB queries

        # ── Generation ───────────────────────────────────────
        report_draft: Generated report content (Markdown)
        report_title: Report title
        report_summary: Executive summary
        review_feedback: Self-review feedback
        query_answer: Natural language answer (for query mode)

        # ── Control ──────────────────────────────────────────
        current_step: Which node is currently executing
        error: Error message if any step fails
        retry_count: Number of retries attempted
        done: Whether the workflow is complete
    """
    # Input
    task_type: Literal["report", "query", "unknown"]
    project_id: str
    user_id: str
    user_input: str
    week_start: str

    # Collected data
    project_info: dict
    progress_records: list[dict]
    documents_text: list[str]
    image_descriptions: list[str]
    sql_results: list[dict]

    # Generation
    report_draft: str
    report_title: str
    report_summary: str
    review_feedback: str
    query_answer: str

    # Control
    current_step: str
    error: str
    retry_count: int
    done: bool