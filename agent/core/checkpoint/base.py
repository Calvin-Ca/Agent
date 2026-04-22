"""Backward-compatible re-exports — canonical module is agent.checkpoint.base."""

from agent.checkpoint.base import CheckpointRecord, CheckpointStore  # noqa: F401

__all__ = ["CheckpointRecord", "CheckpointStore"]
