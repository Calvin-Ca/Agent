"""Node: Data Collector — gather project data from MySQL and Milvus."""

from __future__ import annotations

import time

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
    t0 = time.perf_counter()
    project_info_result = tool_registry.execute("db.get_project_info", project_id=project_id)
    logger.info("[DataCollector] db.get_project_info | {:.0f}ms | success={}", (time.perf_counter() - t0) * 1000, project_info_result.success)
    if not project_info_result.success:
        return {**state, "error": f"项目不存在: {project_id}", "done": True}
    project_info = project_info_result.data

    # 2. Recent progress records
    t0 = time.perf_counter()
    progress_result = tool_registry.execute("db.get_recent_progress", project_id=project_id, weeks=4)
    progress_records = progress_result.data if progress_result.success else []
    logger.info("[DataCollector] db.get_recent_progress | {:.0f}ms | count={}", (time.perf_counter() - t0) * 1000, len(progress_records))

    # 3. Search relevant documents from Milvus
    if task_type == "query":
        query_text = state.get("user_input", "")
    else:
        query_text = f"{project_info.get('name', '')} 本周工作进度 施工情况"

    documents_text = []
    t0 = time.perf_counter()
    try:
        vector_result = tool_registry.execute(
            "vector.search_documents", query=query_text, project_id=project_id, top_k=8,
        )
        documents_text = vector_result.data if vector_result.success else []
        logger.info(
            "[DataCollector] vector.search_documents | {:.0f}ms | query='{}' hits={}",
            (time.perf_counter() - t0) * 1000, query_text[:80], len(documents_text),
        )
    except Exception as e:
        logger.warning("[DataCollector] vector.search_documents FAILED | {:.0f}ms | query='{}' error={}", (time.perf_counter() - t0) * 1000, query_text[:80], e)

    # 4. Previous reports (for report generation context)
    prev_reports = []
    if task_type == "report":
        t0 = time.perf_counter()
        reports_result = tool_registry.execute("db.get_recent_reports", project_id=project_id, limit=2)
        prev_reports = reports_result.data if reports_result.success else []
        logger.info("[DataCollector] db.get_recent_reports | {:.0f}ms | count={}", (time.perf_counter() - t0) * 1000, len(prev_reports))

    # 5. Latest video from MinIO (query mode only)
    latest_video_info = None
    if task_type == "query":
        t0 = time.perf_counter()
        try:
            video_result = tool_registry.execute("minio.get_latest_video")
            if video_result.success:
                latest_video_info = video_result.data
            logger.info("[DataCollector] minio.get_latest_video | {:.0f}ms | found={}", (time.perf_counter() - t0) * 1000, latest_video_info is not None)
        except Exception as e:
            logger.warning("[DataCollector] minio.get_latest_video FAILED | {:.0f}ms | error={}", (time.perf_counter() - t0) * 1000, e)

    logger.info(
        "[DataCollector] SUMMARY | project='{}' task={} | progress={} docs={} prev_reports={} video={}",
        project_info.get("name"), task_type, len(progress_records),
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
