"""Progress request/response schemas."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class ProgressCreate(BaseModel):
    project_id: str
    record_date: date | None = None
    overall_progress: float = Field(0.0, ge=0, le=100)
    milestone: str = Field(default="", max_length=256)
    description: str = ""
    blockers: str = ""
    next_steps: str = ""


class ProgressOut(BaseModel):
    id: str
    project_id: str
    record_date: date
    overall_progress: float
    milestone: str
    description: str
    blockers: str
    next_steps: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProgressQuery(BaseModel):
    """Natural language progress query."""
    project_id: str
    question: str = Field(..., min_length=1, max_length=500, examples=["目前整体进度如何？"])