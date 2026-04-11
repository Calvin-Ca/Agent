"""Unified JSON response format.

All API endpoints should return:
{
    "code": 0,         # 0 = success, >0 = error code
    "message": "ok",
    "data": { ... }
}
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class R(BaseModel, Generic[T]):
    """Standard response envelope."""

    code: int = 0
    message: str = "ok"
    data: T | None = None

    @classmethod
    def ok(cls, data: Any = None, message: str = "ok") -> "R":
        return cls(code=0, message=message, data=data)

    @classmethod
    def fail(cls, code: int = 50000, message: str = "error", data: Any = None) -> "R":
        return cls(code=code, message=message, data=data)


class PageData(BaseModel, Generic[T]):
    """Paginated data wrapper."""

    items: list[T]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size
