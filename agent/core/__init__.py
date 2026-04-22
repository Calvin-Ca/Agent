"""Planning and reasoning core."""

from agent.core.base import AsyncWorkflow, ReasoningNode, ResumableWorkflow, Workflow
from agent.core.context import CostAccumulator, ExecutionContext, current_context, reset_context, set_context
from agent.core.errors import (
    AgentError,
    CheckpointError,
    DataCollectionError,
    GenerationError,
    LLMRateLimitError,
    LLMTimeoutError,
    PlanningError,
    ReviewError,
    ToolExecutionError,
    WorkflowTimeoutError,
)
from agent.core.nodes import (
    data_collector_node,
    progress_query_node,
    report_reviewer_node,
    report_writer_node,
)
from agent.core.planner import BasePlanner, DefaultPlanner, ExecutionPlan, PlanStep, TaskPlanner, planner_node
from agent.core.react_engine import (
    QueryWorkflow,
    ReActEngine,
    ReportWorkflow,
    query_workflow,
    report_workflow,
)
from agent.core.registry import AgentRegistry, agent_registry, auto_discover_agents
from agent.core.state import AgentState, WorkflowState
from agent.core.supervisor import SupervisorState, SupervisorWorkflow, supervisor_workflow


def __getattr__(name: str):
    if name == "AgentLoop":
        from agent.core.agent_loop import AgentLoop

        return AgentLoop
    raise AttributeError(f"module 'agent.core' has no attribute {name!r}")

__all__ = [
    "AgentError",
    "AgentRegistry",
    "AgentLoop",
    "AgentState",
    "AsyncWorkflow",
    "BasePlanner",
    "CheckpointError",
    "CostAccumulator",
    "DataCollectionError",
    "DefaultPlanner",
    "ExecutionPlan",
    "ExecutionContext",
    "GenerationError",
    "LLMRateLimitError",
    "LLMTimeoutError",
    "PlanStep",
    "PlanningError",
    "QueryWorkflow",
    "ReActEngine",
    "ReasoningNode",
    "ResumableWorkflow",
    "ReviewError",
    "ReportWorkflow",
    "SupervisorState",
    "SupervisorWorkflow",
    "TaskPlanner",
    "ToolExecutionError",
    "Workflow",
    "WorkflowState",
    "WorkflowTimeoutError",
    "agent_registry",
    "auto_discover_agents",
    "current_context",
    "data_collector_node",
    "planner_node",
    "progress_query_node",
    "query_workflow",
    "reset_context",
    "report_reviewer_node",
    "report_workflow",
    "report_writer_node",
    "set_context",
    "supervisor_workflow",
]
