"""Tracing middleware — OpenTelemetry span creation for each node.

Creates a child span per node execution, recording key attributes
and linking to the parent trace from ExecutionContext.

TODO: Implement when OpenTelemetry SDK is added to dependencies.
"""

from __future__ import annotations

import functools

from app.agents.state import AgentState
from app.agents.middleware.base import Middleware, NodeFunc


class TracingMiddleware(Middleware):
    """Creates OpenTelemetry spans for each node execution.

    Span attributes:
        - agent.node.name: Node function name
        - agent.project_id: Target project
        - agent.task_type: report / query
        - agent.tenant_id: Tenant identifier
        - agent.request_id: Execution request ID

    TODO: Full implementation requires opentelemetry-api + opentelemetry-sdk.
          Currently passes through without tracing.
    """

    def wrap(self, node_fn: NodeFunc, call_next: NodeFunc) -> NodeFunc:
        @functools.wraps(node_fn)
        def wrapper(state: AgentState) -> AgentState:
            # TODO: Create OTel span here
            # from opentelemetry import trace
            # tracer = trace.get_tracer("agent")
            # ctx = current_context()
            # with tracer.start_as_current_span(
            #     f"node.{node_fn.__name__}",
            #     attributes={
            #         "agent.node.name": node_fn.__name__,
            #         "agent.project_id": state.get("project_id", ""),
            #         "agent.task_type": state.get("task_type", ""),
            #         "agent.tenant_id": ctx.tenant_id,
            #         "agent.request_id": ctx.request_id,
            #     },
            # ) as span:
            #     try:
            #         result = call_next(state)
            #         span.set_attribute("agent.done", result.get("done", False))
            #         return result
            #     except Exception as e:
            #         span.record_exception(e)
            #         span.set_status(StatusCode.ERROR, str(e))
            #         raise

            return call_next(state)

        return wrapper
