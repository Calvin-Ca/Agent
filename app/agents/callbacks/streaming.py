"""Streaming callback — push tokens to SSE / WebSocket connections.

TODO: Implement LangGraph callback handler that:
1. Intercepts LLM token generation events
2. Pushes each token via SSE or WebSocket to the client
3. Supports backpressure and client disconnection
"""

from __future__ import annotations
