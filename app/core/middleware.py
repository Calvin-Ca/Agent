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

from app.observability.logger import build_request_log_filename, generate_request_id, request_log_scope


def register_middleware(app: FastAPI) -> None:
    """Register all middleware on the FastAPI app."""

    # ── CORS ─────────────────────────────────────────────────
    # 浏览器限制 "不同来源的网站互相访问" 的安全机制，一个域包括 "协议 + 域名 + 端口"，有一个不同就是跨域
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
        # Skip noisy endpoints
        path = request.url.path
        if path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)

        # Generate and set request ID
        rid = request.headers.get("X-Request-ID") or generate_request_id()
        uid = _extract_user_id(request)

        # Per-request log file under logs/
        import time as _time

        inv_ts = 9999999999 - int(_time.time())
        request_log_file = build_request_log_filename(rid, inv_ts)

        with request_log_scope(
            request_id=rid,
            user_id=uid or "-",
            request_log_file=request_log_file,
        ):
            # Client IP
            client_ip = request.client.host if request.client else "unknown"
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                client_ip = forwarded.split(",")[0].strip()

            # Read request body for logging (only for relevant content types)
            request_body_summary = ""
            if request.method in ("POST", "PUT", "PATCH"):
                content_type = request.headers.get("content-type", "")
                if "application/json" in content_type:
                    body_bytes = await request.body()
                    request_body_summary = _truncate(body_bytes.decode("utf-8", errors="replace"), 500)
                elif "multipart/form-data" in content_type:
                    request_body_summary = "[multipart/form-data]"
                elif "application/x-www-form-urlencoded" in content_type:
                    body_bytes = await request.body()
                    request_body_summary = _truncate(body_bytes.decode("utf-8", errors="replace"), 500)

            logger.info(
                "→ {method} {path} | ip={ip} | body={body}",
                method=request.method,
                path=path,
                ip=client_ip,
                body=request_body_summary or "-",
            )

            start = time.perf_counter()
            response: Response | None = None
            try:
                response = await call_next(request)
                return response
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                status = response.status_code if response else 500

                logger.info(
                    "← {method} {path} → {status} ({elapsed:.0f}ms)",
                    method=request.method,
                    path=path,
                    status=status,
                    elapsed=elapsed_ms,
                )

                # Inject tracing headers into response
                if response:
                    response.headers["X-Request-ID"] = rid
                    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.0f}"


def _extract_user_id(request: Request) -> str:
    """Best-effort extract user ID from Bearer token."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        try:
            from app.core.security import decode_access_token
            payload = decode_access_token(auth.removeprefix("Bearer ").strip())
            return str(payload.get("sub", ""))
        except Exception:
            pass
    return ""


def _get_client_id(request: Request) -> str:
    """Extract client identifier for rate limiting."""
    # Try to get user ID from Authorization header
    uid = _extract_user_id(request)
    if uid:
        return f"user:{uid}"

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


def _truncate(s: str, max_len: int) -> str:
    """Truncate a string and append '...' if it exceeds max_len."""
    if len(s) <= max_len:
        return s
    return s[:max_len] + "..."
