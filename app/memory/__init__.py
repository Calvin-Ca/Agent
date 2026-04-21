"""Memory system — multi-layer memory architecture.

Layers:
    - structured: MySQL — project info, progress, reports (CRUD)
    - long_term: Milvus — document embeddings for semantic search
    - short_term: Redis — request/session caching
    - conversation: Multi-turn dialogue history per session
    - episodic: Task execution history for experience-based learning
    - summary: Conversation summarization for context compression

Usage:
    from app.memory.manager import memory_manager

    # Structured data
    info = memory_manager.structured.get_project_info(project_id)
    # Semantic search
    chunks = memory_manager.long_term.search(query, project_id)
    # Cache
    cached = await memory_manager.short_term.get(key)

    # Conversation history (direct import)
    from app.memory.conversation import conversation_memory
    history = conversation_memory.get_history(session_id)

    # Episodic memory (direct import)
    from app.memory.episodic import episodic_memory
    episodes = episodic_memory.recall(project_id=pid, task_type="report")
"""
