"""Middleware stack — CORS, request logging, rate limiting.

Rate limiting uses Redis token bucket per user (by IP or JWT user ID).
"""

from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger


def register_middleware(app: FastAPI) -> None:
    """Register all middleware on the FastAPI app."""

    # ── CORS ─────────────────────────────────────────────────
    # 浏览器限制 “不同来源的网站互相访问” 的安全机制，一个域包括 “协议 + 域名 + 端口”，有一个不同就是跨域
    # 例如 http://localhost:3000 和 http://localhost:8000
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],    # 允许哪些前端，只有这里写的前端，才能访问你的后端：所有来源（开发用）
        allow_credentials=True, # 是否允许 cookie
        allow_methods=["*"],    # 允许的方法：GET / POST 等获取/发布等
        allow_headers=["*"],
    )

    # ── Rate Limiting ────────────────────────────────────────
    @app.middleware("http")
    async def rate_limit(request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for health check and docs
        path = request.url.path
        if path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        # Identify client: prefer user ID from token, fallback to IP
        client_id = _get_client_id(request)

        # Check rate limit (60 requests per minute per client)
        allowed = await _check_rate_limit(client_id, max_requests=60, window_seconds=60)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"code": 42900, "message": "请求过于频繁，请稍后再试", "data": None},
            )

        return await call_next(request)

    # ── Request Logging ──────────────────────────────────────
    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "{method} {path} → {status} ({elapsed:.0f}ms)",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed=elapsed_ms,
        )
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.0f}"
        return response


def _get_client_id(request: Request) -> str:
    """Extract client identifier for rate limiting."""
    # Try to get user ID from Authorization header
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(auth.removeprefix("Bearer ").strip())
            user_id = payload.get("sub", "")
            if user_id:
                return f"user:{user_id}"
        except Exception:
            pass

    # Fallback to IP
    client_ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    return f"ip:{client_ip}"


async def _check_rate_limit(client_id: str, max_requests: int, window_seconds: int) -> bool:
    """Token bucket rate limiter using Redis.

    Returns True if request is allowed, False if rate limited.
    """
    try:
        from app.db.redis import get_redis

        r = get_redis()
        key = f"ratelimit:{client_id}"

        # Increment counter
        current = await r.incr(key)

        # Set TTL on first request
        if current == 1:
            await r.expire(key, window_seconds)

        return current <= max_requests

    except Exception as e:
        # If Redis is down, allow the request (fail open)
        logger.warning("Rate limit check failed (allowing request): {}", e)
        return True