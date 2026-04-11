"""User request/response schemas."""
# 数据校验（请求进来时，json2python）与序列化（响应返回时，python2json）

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# ── Requests ─────────────────────────────────────────────────
# 数据校验 = 检查前端传来的数据是否符合规则
# 比如用户名太短、邮箱格式错误、密码太短等

class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=64, examples=["zhangsan"])
    email: EmailStr = Field(..., examples=["zhangsan@example.com"])
    password: str = Field(..., min_length=6, max_length=128)
    nickname: str = Field(default="", max_length=64)


class UserLogin(BaseModel):
    username: str = Field(..., examples=["zhangsan"])
    password: str = Field(...)


class UserUpdate(BaseModel):
    nickname: str | None = None
    email: EmailStr | None = None


# ── Responses ────────────────────────────────────────────────
# 将返回的 python对象变json
# 例如 return UserOut.model_validate(user) 自动把 user 变成 json 格式

class UserOut(BaseModel):
    id: str
    username: str
    email: str
    nickname: str
    role: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut