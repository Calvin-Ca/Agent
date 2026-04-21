"""Upload request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel # pydantic : 用 Python 类型来做数据校验 + 数据转换


class UploadOut(BaseModel):
    id: str
    project_id: str
    filename: str
    file_type: str
    file_size: int
    process_status: int
    created_at: datetime

    model_config = {"from_attributes": True} # 允许 Pydantic 从“对象属性（ORM）”读取数据，而不是只能从 dict 读取