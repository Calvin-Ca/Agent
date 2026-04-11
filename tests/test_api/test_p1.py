"""P1 integration tests — Auth, Project CRUD, Upload.

Usage:
    pytest tests/test_api/test_p1.py -v
    pytest tests/test_api/test_p1.py -v -k auth
    pytest tests/test_api/test_p1.py -v -k project
"""

from __future__ import annotations

import io
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


# ══════════════════════════════════════════════════════════════
# Project CRUD
# ══════════════════════════════════════════════════════════════

class TestProject:

    async def test_create_project(self, authed_client: AsyncClient):
        resp = await authed_client.post(f"{V1}/projects", json={
            "name": "测试项目",
            "code": "TST-001",
            "description": "P1集成测试用项目",
        })
        data = resp.json()
        if data["code"] == 0:
            assert data["data"]["name"] == "测试项目"
            assert data["data"]["code"] == "TST-001"

    async def test_list_projects(self, authed_client: AsyncClient):
        resp = await authed_client.get(f"{V1}/projects")
        data = resp.json()
        assert data["code"] == 0
        assert "items" in data["data"]
        assert isinstance(data["data"]["total"], int)

    async def test_get_project(self, authed_client: AsyncClient):
        # Create first
        create_resp = await authed_client.post(f"{V1}/projects", json={
            "name": "详情测试",
            "code": "TST-DETAIL",
        })
        if create_resp.json()["code"] != 0:
            pytest.skip("Could not create project (likely duplicate code)")

        pid = create_resp.json()["data"]["id"]
        resp = await authed_client.get(f"{V1}/projects/{pid}")
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["id"] == pid

    async def test_update_project(self, authed_client: AsyncClient):
        create_resp = await authed_client.post(f"{V1}/projects", json={
            "name": "更新前",
            "code": "TST-UPD",
        })
        if create_resp.json()["code"] != 0:
            pytest.skip("Could not create project")

        pid = create_resp.json()["data"]["id"]
        resp = await authed_client.put(f"{V1}/projects/{pid}", json={
            "name": "更新后",
            "description": "已更新描述",
        })
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["name"] == "更新后"

    async def test_delete_project(self, authed_client: AsyncClient):
        create_resp = await authed_client.post(f"{V1}/projects", json={
            "name": "待删除",
            "code": "TST-DEL",
        })
        if create_resp.json()["code"] != 0:
            pytest.skip("Could not create project")

        pid = create_resp.json()["data"]["id"]
        resp = await authed_client.delete(f"{V1}/projects/{pid}")
        assert resp.json()["code"] == 0

        # Verify soft-deleted
        resp = await authed_client.get(f"{V1}/projects/{pid}")
        assert resp.json()["code"] == 40400  # not found

    async def test_project_not_found(self, authed_client: AsyncClient):
        resp = await authed_client.get(f"{V1}/projects/nonexistent_id")
        assert resp.json()["code"] == 40400


# ══════════════════════════════════════════════════════════════
# Upload
# ══════════════════════════════════════════════════════════════

class TestUpload:

    async def test_upload_text_file(self, authed_client: AsyncClient):
        # Create project first
        proj_resp = await authed_client.post(f"{V1}/projects", json={
            "name": "上传测试项目",
            "code": "TST-UPLOAD",
        })
        if proj_resp.json()["code"] != 0:
            # Use existing project
            list_resp = await authed_client.get(f"{V1}/projects?page_size=1")
            items = list_resp.json()["data"]["items"]
            if not items:
                pytest.skip("No project available for upload test")
            pid = items[0]["id"]
        else:
            pid = proj_resp.json()["data"]["id"]

        file_content = "这是一份测试文本文件\n包含中文内容".encode("utf-8")
        resp = await authed_client.post(
            f"{V1}/upload",
            data={"project_id": pid},
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["file_type"] == "text"
        assert data["data"]["process_status"] == 0  # pending

    async def test_upload_unsupported_type(self, authed_client: AsyncClient):
        list_resp = await authed_client.get(f"{V1}/projects?page_size=1")
        items = list_resp.json()["data"]["items"]
        if not items:
            pytest.skip("No project available")
        pid = items[0]["id"]

        resp = await authed_client.post(
            f"{V1}/upload",
            data={"project_id": pid},
            files={"file": ("test.exe", io.BytesIO(b"binary"), "application/octet-stream")},
        )
        assert resp.json()["code"] == 40010

    async def test_upload_dedup(self, authed_client: AsyncClient):
        """Same file uploaded twice should be deduped."""
        list_resp = await authed_client.get(f"{V1}/projects?page_size=1")
        items = list_resp.json()["data"]["items"]
        if not items:
            pytest.skip("No project available")
        pid = items[0]["id"]

        content = b"dedup test content 12345"
        for _ in range(2):
            resp = await authed_client.post(
                f"{V1}/upload",
                data={"project_id": pid},
                files={"file": ("dedup.txt", io.BytesIO(content), "text/plain")},
            )
        # Second upload should say "already exists"
        assert "已存在" in resp.json().get("message", "")