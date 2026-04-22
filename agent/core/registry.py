"""Backward-compatible re-exports — canonical module is agent.planning.registry."""

from agent.planning.registry import AgentRegistry, agent_registry, auto_discover_agents  # noqa: F401

__all__ = ["AgentRegistry", "agent_registry", "auto_discover_agents"]
