"""Node: Data Collector — gather project data from MySQL and Milvus."""

from __future__ import annotations

from loguru import logger

from app.agents.state import AgentState
from app.agents.tools.db_query import (
    get_project_info,
    get_recent_progress,
    get_recent_reports,
)
from app.agents.tools.vector_search import search_documents


def data_collector_node(state: AgentState) -> AgentState:
    """Collect all relevant data for report generation or query answering."""
    project_id = state["project_id"]
    task_type = state.get("task_type", "report")

    logger.info("DataCollector: gathering data for project {}", project_id)

    # 1. Project info from MySQL
    project_info = get_project_info(project_id)
    if not project_info:
        return {**state, "error": f"项目不存在: {project_id}", "done": True}

    # 2. Recent progress records
    progress_records = get_recent_progress(project_id, weeks=4)

    # 3. Search relevant documents from Milvus
    if task_type == "query":
        # Use user's question as search query
        query_text = state.get("user_input", "")
    else:
        # For reports, search with project context
        query_text = f"{project_info.get('name', '')} 本周工作进度 施工情况"

    documents_text = []
    try:
        documents_text = search_documents(query_text, project_id, top_k=8)
    except Exception as e:
        logger.warning("Vector search failed (non-fatal): {}", e)

    # 4. Previous reports (for report generation context)
    prev_reports = []
    if task_type == "report":
        prev_reports = get_recent_reports(project_id, limit=2)

    logger.info(
        "DataCollector: project='{}', progress={}, docs={}, prev_reports={}",
        project_info.get("name"), len(progress_records),
        len(documents_text), len(prev_reports),
    )

    return {
        **state,
        "project_info": project_info,
        "progress_records": progress_records,
        "documents_text": documents_text,
        "sql_results": prev_reports,
        "current_step": "data_collector",
    }