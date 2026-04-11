"""Node: Progress Query — answer natural language questions via RAG + LLM."""

from __future__ import annotations

from loguru import logger

from app.agents.state import AgentState
from app.agents.prompts.templates import QUERY_SYSTEM, build_query_prompt
from app.model_service.llm import llm_generate


def progress_query_node(state: AgentState) -> AgentState:
    """Answer a natural language question about project progress."""
    user_input = state.get("user_input", "")
    project_info = state.get("project_info", {})
    progress_records = state.get("progress_records", [])
    documents_text = state.get("documents_text", [])

    if not user_input:
        return {**state, "error": "缺少查询问题", "done": True}

    logger.info("ProgressQuery: '{}'", user_input[:50])

    prompt = build_query_prompt(
        question=user_input,
        project_info=project_info,
        progress_records=progress_records,
        documents_text=documents_text,
    )

    try:
        answer = llm_generate(
            prompt=prompt,
            system=QUERY_SYSTEM,
            max_tokens=1024,
            temperature=0.3,
        )
    except Exception as e:
        logger.error("Query LLM failed: {}", e)
        return {**state, "error": f"查询失败: {e}", "done": True}

    logger.info("ProgressQuery: answer {} chars", len(answer))

    return {
        **state,
        "query_answer": answer,
        "current_step": "progress_query",
        "done": True,
    }