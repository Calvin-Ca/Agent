"""Product-facing API tests — auth + chat only."""

from __future__ import annotations

import io
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"
V1 = "/api/v1"


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url=BASE) as c:
        yield c


@pytest.fixture
async def authed_client(client: AsyncClient):
    """Register a test user and return client with auth header."""
    resp = await client.post(f"{V1}/auth/register", json={
        "username": "testuser_p1",
        "email": "testuser_p1@test.com",
        "password": "test123456",
        "nickname": "Test P1",
    })
    # might already exist from a previous test run
    if resp.status_code == 200 and resp.json()["code"] == 0:
        token = resp.json()["data"]["access_token"]
    else:
        # Login instead
        resp = await client.post(f"{V1}/auth/login", json={
            "username": "testuser_p1",
            "password": "test123456",
        })
        assert resp.json()["code"] == 0, f"Login failed: {resp.json()}"
        token = resp.json()["data"]["access_token"]

    client.headers["Authorization"] = f"Bearer {token}"
    yield client


# ══════════════════════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════════════════════

class TestAuth:

    async def test_register(self, client: AsyncClient):
        resp = await client.post(f"{V1}/auth/register", json={
            "username": "auth_test_user",
            "email": "auth_test@test.com",
            "password": "password123",
        })
        data = resp.json()
        # Either success or already exists
        assert data["code"] in (0, 40001, 40002)
        if data["code"] == 0:
            assert "access_token" in data["data"]
            assert data["data"]["user"]["username"] == "auth_test_user"

    async def test_login(self, client: AsyncClient):
        # Ensure user exists
        await client.post(f"{V1}/auth/register", json={
            "username": "login_test_user",
            "email": "login_test@test.com",
            "password": "password123",
        })
        resp = await client.post(f"{V1}/auth/login", json={
            "username": "login_test_user",
            "password": "password123",
        })
        data = resp.json()
        assert data["code"] == 0
        assert "access_token" in data["data"]

    async def test_login_wrong_password(self, client: AsyncClient):
        resp = await client.post(f"{V1}/auth/login", json={
            "username": "login_test_user",
            "password": "wrongpassword",
        })
        assert resp.json()["code"] == 40100

    async def test_me(self, authed_client: AsyncClient):
        resp = await authed_client.get(f"{V1}/auth/me")
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["username"] == "testuser_p1"

    async def test_me_no_token(self, client: AsyncClient):
        resp = await client.get(f"{V1}/auth/me")
        assert resp.status_code == 422  # missing header


def _mock_intent(monkeypatch: pytest.MonkeyPatch, intent: str, params: dict | None = None):
    async def fake_run_in_executor(*_args, **_kwargs):
        return {"intent": intent, "params": params or {}}

    monkeypatch.setattr(
        "app.services.chat_service.run_in_executor_with_context",
        fake_run_in_executor,
    )


class TestChat:

    async def test_create_project_via_chat(self, authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
        project_name = f"聊天创建项目-{uuid4().hex[:8]}"
        _mock_intent(
            monkeypatch,
            "create_project",
            {"name": project_name, "code": f"CHAT-{uuid4().hex[:6]}"},
        )

        resp = await authed_client.post(
            f"{V1}/chat",
            data={"prompt": f"创建项目 {project_name}"},
        )
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["intent"] == "create_project"
        assert data["data"]["data"]["name"] == project_name

    async def test_list_projects_via_chat(self, authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
        _mock_intent(monkeypatch, "list_projects")

        resp = await authed_client.post(
            f"{V1}/chat",
            data={"prompt": "查看我的项目"},
        )
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["intent"] == "list_projects"
        assert isinstance(data["data"]["data"], list)

    async def test_upload_rejects_unsupported_type_via_chat(
        self,
        authed_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ):
        project_name = f"上传测试项目-{uuid4().hex[:8]}"
        create_code = f"UP-{uuid4().hex[:6]}"

        _mock_intent(
            monkeypatch,
            "create_project",
            {"name": project_name, "code": create_code},
        )
        create_resp = await authed_client.post(
            f"{V1}/chat",
            data={"prompt": f"创建项目 {project_name}"},
        )
        assert create_resp.json()["code"] == 0

        _mock_intent(
            monkeypatch,
            "upload_file",
            {"project_name": project_name},
        )
        resp = await authed_client.post(
            f"{V1}/chat",
            data={"prompt": f"把文件上传到项目 {project_name}"},
            files={"file": ("bad.exe", io.BytesIO(b"binary"), "application/octet-stream")},
        )
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["intent"] == "upload_file"
        assert "不支持的文件类型" in data["data"]["message"]
