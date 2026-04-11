"""Project request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, examples=["城南花园三期"])
    code: str = Field(..., min_length=1, max_length=32, examples=["PRJ-001"])
    description: str = Field(default="", max_length=2000)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    status: int | None = Field(default=None, ge=0, le=2)


class ProjectOut(BaseModel):
    id: str
    name: str
    code: str
    description: str
    status: int
    owner_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}