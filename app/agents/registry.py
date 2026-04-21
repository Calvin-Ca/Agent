"""Agent registry — maps agent names to graph factories.

Usage:
    from app.agents.registry import agent_registry

    graph = agent_registry.get("report")
    result = graph.run(project_id="xxx", user_id="yyy")
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from app.agents.base import Workflow


class AgentRegistry:
    """Central registry for agent workflows (name → Workflow instance)."""

    def __init__(self):
        self._agents: dict[str, Workflow] = {}

    def register(self, name: str, workflow: Workflow) -> None:
        """Register an agent workflow by name."""
        self._agents[name] = workflow
        logger.info("Registered agent: {}", name)

    def get(self, name: str) -> Workflow:
        """Get an agent workflow by name. Raises KeyError if not found."""
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' not registered. Available: {list(self._agents.keys())}")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        """Return all registered agent names."""
        return list(self._agents.keys())


# Singleton
agent_registry = AgentRegistry()


def auto_discover_agents() -> None:
    """Register all built-in agent workflows. Called at app startup."""
    from app.agents.graphs.report_graph import report_workflow
    from app.agents.graphs.query_graph import query_workflow
    from app.agents.graphs.supervisor import supervisor_workflow

    agent_registry.register("report", report_workflow)
    agent_registry.register("query", query_workflow)
    agent_registry.register("supervisor", supervisor_workflow)

    logger.info("Agent registry: {} agents registered", len(agent_registry.list_agents()))
