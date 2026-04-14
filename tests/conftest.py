"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import asyncio
import sys

import pytest
from httpx import ASGITransport, AsyncClient

# Windows ProactorEventLoop is incompatible with aiomysql and some asyncio patterns
# (BaseHTTPMiddleware pending tasks, _proactor=None on close). Force SelectorEventLoop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.main import app

V1 = "/api/v1"


@pytest.fixture(scope="session")
async def client():
    """Single AsyncClient for the whole session — app lifespan runs exactly once."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture(scope="session")
async def _auth_token(client: AsyncClient) -> str:
    """Obtain a JWT token once for the session."""
    resp = await client.post(f"{V1}/auth/register", json={
        "username": "test_runner",
        "email": "test_runner@test.com",
        "password": "testpass123",
        "nickname": "Test Runner",
    })
    if resp.json()["code"] == 0:
        return resp.json()["data"]["access_token"]

    resp = await client.post(f"{V1}/auth/login", json={
        "username": "test_runner",
        "password": "testpass123",
    })
    assert resp.json()["code"] == 0, f"Login failed: {resp.json()}"
    return resp.json()["data"]["access_token"]


@pytest.fixture
def authed_client(client: AsyncClient, _auth_token: str):
    """Yield the shared client with Authorization header, restore after each test."""
    client.headers["Authorization"] = f"Bearer {_auth_token}"
    yield client
    del client.headers["Authorization"]
