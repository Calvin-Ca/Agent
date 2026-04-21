"""Workflow registry for agent execution entry points."""

from __future__ import annotations

from loguru import logger

from agent.core.base import Workflow


class AgentRegistry:
    """Central registry for named agent workflows."""

    def __init__(self) -> None:
        self._agents: dict[str, Workflow] = {}

    def register(self, name: str, workflow: Workflow) -> None:
        self._agents[name] = workflow
        logger.info("Registered agent: {}", name)

    def get(self, name: str) -> Workflow:
        if name not in self._agents:
            raise KeyError(f"Agent '{name}' not registered. Available: {list(self._agents.keys())}")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())


agent_registry = AgentRegistry()


def auto_discover_agents() -> None:
    """Register built-in workflows."""
    from agent.core.react_engine import query_workflow, report_workflow
    from agent.core.supervisor import supervisor_workflow

    agent_registry.register("report", report_workflow)
    agent_registry.register("query", query_workflow)
    agent_registry.register("supervisor", supervisor_workflow)

    logger.info("Agent registry: {} agents registered", len(agent_registry.list_agents()))


__all__ = ["AgentRegistry", "agent_registry", "auto_discover_agents"]
