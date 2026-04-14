"""Layer 7: Memory — unified abstraction over structured (MySQL), vector (Milvus), and cache (Redis) stores.

Usage:
    from app.memory import unified_memory

    info = unified_memory.structured.get_project_info(project_id)
    chunks = unified_memory.vector.search(query, project_id)
    cached = await unified_memory.cache.get(key)
"""
