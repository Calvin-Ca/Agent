"""Agent callbacks — logging, metrics, and streaming for LangGraph nodes.

Decorators (apply in this order, outermost first):

    @stream_node    ← emits SSE/WebSocket node_start/node_end events
    @log_node       ← logs timing and state transitions via loguru
    @metrics_node   ← records Prometheus histograms/counters
    def my_node(state: AgentState) -> AgentState: ...

Standalone helpers:
    stream_event(event_type, data)  — push a custom event to the stream queue
    set_stream_queue(queue)         — bind an asyncio.Queue for a request
    reset_stream_queue(token)       — unbind after request completes
    record_llm_call(...)            — record LLM metrics from model_service
    record_workflow(...)            — record end-to-end workflow metrics
"""

from app.agents.callbacks.logging import log_node
from app.agents.callbacks.metrics import metrics_node, record_llm_call, record_workflow
from app.agents.callbacks.streaming import (
    stream_node,
    stream_event,
    set_stream_queue,
    reset_stream_queue,
    get_stream_queue,
)

__all__ = [
    # Decorators
    "log_node",
    "metrics_node",
    "stream_node",
    # Streaming helpers
    "stream_event",
    "set_stream_queue",
    "reset_stream_queue",
    "get_stream_queue",
    # Metrics helpers
    "record_llm_call",
    "record_workflow",
]
