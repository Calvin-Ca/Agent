"""Chat request/response schemas — unified endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Unified chat request. Only prompt is required."""

    prompt: str = Field(..., min_length=1, max_length=2000, examples=["帮我创建一个项目，名称叫城南花园三期"])
    project_id: str | None = Field(default=None, description="目标项目ID，部分操作需要")


class IntentResult(BaseModel):
    """LLM intent recognition output."""

    intent: str
    params: dict = {}
    confidence: float = 1.0


class ChatResponse(BaseModel):
    """Unified chat response."""

    intent: str = Field(description="识别到的意图")
    message: str = Field(description="对用户的回复文本")
    data: dict | list | None = Field(default=None, description="结构化数据（如有）")
