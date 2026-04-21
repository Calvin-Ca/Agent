"""Global exception hierarchy and FastAPI exception handlers.

Usage:
    raise BizError(code=40001, message="项目不存在")
    raise AuthError("token已过期")
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from fastapi import FastAPI


# ── Exception Hierarchy ──────────────────────────────────────


class AppError(Exception):
    """Base application exception."""

    def __init__(self, code: int = 50000, message: str = "内部错误", status_code: int = 500):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class BizError(AppError):
    """Business logic error (4xx)."""

    def __init__(self, code: int = 40000, message: str = "业务错误", status_code: int = 400):
        super().__init__(code=code, message=message, status_code=status_code)


class NotFoundError(BizError):
    """Resource not found."""

    def __init__(self, message: str = "资源不存在"):
        super().__init__(code=40400, message=message, status_code=404)


class AuthError(BizError):
    """Authentication / authorization error."""

    def __init__(self, message: str = "认证失败"):
        super().__init__(code=40100, message=message, status_code=401)


class RateLimitError(BizError):
    """Rate limit exceeded."""

    def __init__(self, message: str = "请求过于频繁，请稍后再试"):
        super().__init__(code=42900, message=message, status_code=429)


# ── Handlers ─────────────────────────────────────────────────


def register_exception_handlers(app: "FastAPI") -> None:
    """Register all exception handlers on the FastAPI app."""
    from fastapi import Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse

    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        logger.warning("AppError [{}]: {}", exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message, "data": None},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        first_error = exc.errors()[0] if exc.errors() else {}
        field = " -> ".join(str(loc) for loc in first_error.get("loc", []))
        msg = first_error.get("msg", "参数校验失败")
        return JSONResponse(
            status_code=422,
            content={
                "code": 42200,
                "message": f"参数错误: {field} — {msg}",
                "data": None,
            },
        )

    @app.exception_handler(Exception)
    async def global_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: {}", exc)
        return JSONResponse(
            status_code=500,
            content={"code": 50000, "message": "服务器内部错误", "data": None},
        )
