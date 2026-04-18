"""Memory system — structured (MySQL), long-term (Milvus), short-term (Redis).

Usage:
    from app.memory.manager import memory_manager

    info = memory_manager.structured.get_project_info(project_id)
    chunks = memory_manager.long_term.search(query, project_id)
    cached = await memory_manager.short_term.get(key)
"""
