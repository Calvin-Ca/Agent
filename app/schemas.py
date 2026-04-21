"""Top-level request/response schema contracts for the API layer.

Domain-specific schemas live in app/schema_defs/ and should be imported
from there directly (e.g. ``from app.schema_defs.chat import ChatResponse``).
This module re-exports only the primary platform-level types.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.core.response import R
from app.schema_defs.chat import ChatRequest, ChatResponse


class StreamRequest(ChatRequest):
    """Streaming chat request — extends the shared ChatRequest."""

    stream: bool = Field(default=True)


class HealthPayload(BaseModel):
    """Health response payload."""

    status: str
    env: str
    app: str


class StreamEvent(BaseModel):
    """Server-sent event payload."""

    event: str
    data: dict | list | str | None = None


HealthResponse = R[HealthPayload]
ChatEnvelope = R[ChatResponse]

__all__ = [
    "ChatEnvelope",
    "ChatRequest",
    "ChatResponse",
    "HealthPayload",
    "HealthResponse",
    "StreamEvent",
    "StreamRequest",
]
