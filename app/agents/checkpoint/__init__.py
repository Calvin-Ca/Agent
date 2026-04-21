"""Checkpoint — persist and restore workflow state for resumable execution.

Enables long-running workflows to survive process restarts, and allows
users to resume a failed workflow from the last successful node.

Usage:
    from app.agents.checkpoint import CheckpointStore, RedisCheckpointStore

    store = RedisCheckpointStore()
    # Save state after each node completes
    store.save(thread_id="run-123", node="data_collector", state=current_state)
    # Resume from last checkpoint
    state, node = store.load_latest(thread_id="run-123")
"""

from app.agents.checkpoint.base import CheckpointStore, CheckpointRecord
from app.agents.checkpoint.redis_store import RedisCheckpointStore

__all__ = [
    "CheckpointStore",
    "CheckpointRecord",
    "RedisCheckpointStore",
]
