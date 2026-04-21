"""Agent core — LangGraph graphs, nodes, tools, prompts, middleware.

Enterprise architecture:
    - graphs/: LangGraph state machines (report, query, supervisor)
    - nodes/: Node implementations (planner, data_collector, etc.)
    - middleware/: Composable cross-cutting concerns (logging, metrics, tracing, retry)
    - checkpoint/: Workflow state persistence for resumable execution
    - callbacks/: Legacy decorators (backward compatible, prefer middleware for new code)
    - planner/: Planner implementations
    - prompts/: Prompt templates
    - context.py: Request-scoped execution context
    - errors.py: Agent-specific exception hierarchy
    - state.py: AgentState TypedDict
    - base.py: Workflow protocol
    - registry.py: Agent workflow registry
"""

from app.agents.graphs.report_graph import report_workflow
from app.agents.graphs.query_graph import query_workflow
from app.agents.context import ExecutionContext, current_context, set_context, reset_context
from app.agents.errors import AgentError

__all__ = [
    "report_workflow",
    "query_workflow",
    "ExecutionContext",
    "current_context",
    "set_context",
    "reset_context",
    "AgentError",
]
