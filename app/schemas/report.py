"""Report request/response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ReportGenerate(BaseModel):
    project_id: str = Field(..., examples=["a1b2c3d4..."])
    week_start: date | None = Field(default=None, description="Auto-detect if omitted")


class ReportOut(BaseModel):
    id: str
    project_id: str
    creator_id: str
    title: str
    week_start: date
    week_end: date
    content: str
    summary: str
    status: int
    export_path: str
    created_at: datetime

    model_config = {"from_attributes": True}