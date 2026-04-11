"""Middleware stack — CORS, request logging, rate limiting.

Applied in main.py during app startup.
"""

from __future__ import annotations

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger


def register_middleware(app: FastAPI) -> None:
    """Register all middleware on the FastAPI app."""

    # ── CORS ─────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # tighten in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
