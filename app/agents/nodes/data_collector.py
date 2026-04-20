"""Node: Data Collector — gather project data from MySQL and Milvus."""

from __future__ import annotations

from loguru import logger

from app.agents.state import AgentState
from app.agents.callbacks.logging import log_node
from app.tools.registry import tool_registry


@log_node
def data_collector_node(state: AgentState) -> AgentState:
    """Collect all relevant data for report generation or query answering."""
    project_id = state["project_id"]
    task_type = state.get("task_type", "report")

    logger.info("DataCollector: gathering data for project {}", project_id)

    # 1. Project info from MySQL
    project_info_result = tool_registry.execute("db.get_project_info", project_id=project_id)
    if not project_info_result.success:
        return {**state, "error": f"项目不存在: {project_id}", "done": True}
    project_info = project_info_result.data

    # 2. Recent progress records
    progress_result = tool_registry.execute("db.get_recent_progress", project_id=project_id, weeks=4)
    progress_records = progress_result.data if progress_result.success else []

    # 3. Search relevant documents from Milvus
    if task_type == "query":
        # Use user's question as search query
        query_text = state.get("user_input", "")
    else:
        # For reports, search with project context
        query_text = f"{project_info.get('name', '')} 本周工作进度 施工情况"

    documents_text = []
    try:
        vector_result = tool_registry.execute(
            "vector.search_documents", query=query_text, project_id=project_id, top_k=8,
        )
        documents_text = vector_result.data if vector_result.success else []
    except Exception as e:
        logger.warning("Vector search failed (non-fatal): {}", e)

    # 4. Previous reports (for report generation context)
    prev_reports = []
    if task_type == "report":
        reports_result = tool_registry.execute("db.get_recent_reports", project_id=project_id, limit=2)
        prev_reports = reports_result.data if reports_result.success else []

    # 5. Latest video from MinIO (query mode only)
    latest_video_info = None
    if task_type == "query":
        try:
            video_result = tool_registry.execute("minio.get_latest_video")
            if video_result.success:
                latest_video_info = video_result.data  # may be None if no videos exist
        except Exception as e:
            logger.warning("MinIO video query failed (non-fatal): {}", e)

    logger.info(
        "DataCollector: project='{}', progress={}, docs={}, prev_reports={}, video={}",
        project_info.get("name"), len(progress_records),
        len(documents_text), len(prev_reports),
        latest_video_info.get("filename") if latest_video_info else "无",
    )

    return {
        **state,
        "project_info": project_info,
        "progress_records": progress_records,
        "documents_text": documents_text,
        "sql_results": prev_reports,
        "latest_video_info": latest_video_info,
        "current_step": "data_collector",
    }
