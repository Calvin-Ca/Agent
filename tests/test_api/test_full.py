"""API integration tests for report and progress endpoints."""

from __future__ import annotations

import io
import pytest
from httpx import AsyncClient


V1 = "/api/v1"


class TestReportAPI:

    async def test_list_reports_empty(self, authed_client: AsyncClient):
        resp = await authed_client.get(f"{V1}/reports")
        data = resp.json()
        assert data["code"] == 0
        assert "items" in data["data"]

    async def test_list_reports_with_project_filter(self, authed_client: AsyncClient):
        resp = await authed_client.get(f"{V1}/reports?project_id=nonexistent")
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["total"] == 0

    async def test_get_report_not_found(self, authed_client: AsyncClient):
        resp = await authed_client.get(f"{V1}/reports/nonexistent_id")
        assert resp.json()["code"] == 40400

    async def test_generate_requires_valid_project(self, authed_client: AsyncClient):
        resp = await authed_client.post(f"{V1}/reports/generate", json={
            "project_id": "nonexistent_id",
        })
        assert resp.json()["code"] == 40400


class TestProgressAPI:

    async def _get_project_id(self, client: AsyncClient) -> str:
        resp = await client.get(f"{V1}/projects?page_size=1")
        items = resp.json()["data"]["items"]
        if not items:
            # Create one
            resp = await client.post(f"{V1}/projects", json={
                "name": "进度测试项目", "code": "TST-PROG",
            })
            if resp.json()["code"] == 0:
                return resp.json()["data"]["id"]
            # Try list again
            resp = await client.get(f"{V1}/projects?page_size=1")
            items = resp.json()["data"]["items"]
        return items[0]["id"] if items else ""

    async def test_create_progress(self, authed_client: AsyncClient):
        pid = await self._get_project_id(authed_client)
        if not pid:
            pytest.skip("No project available")

        resp = await authed_client.post(f"{V1}/progress", json={
            "project_id": pid,
            "overall_progress": 55.0,
            "milestone": "基础施工",
            "description": "本周完成基础浇筑",
            "next_steps": "下周开始主体",
        })
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["overall_progress"] == 55.0

    async def test_list_progress(self, authed_client: AsyncClient):
        pid = await self._get_project_id(authed_client)
        if not pid:
            pytest.skip("No project available")

        resp = await authed_client.get(f"{V1}/progress?project_id={pid}")
        data = resp.json()
        assert data["code"] == 0
        assert "items" in data["data"]

    async def test_query_requires_valid_project(self, authed_client: AsyncClient):
        resp = await authed_client.post(f"{V1}/progress/query", json={
            "project_id": "nonexistent",
            "question": "进度如何？",
        })
        assert resp.json()["code"] == 40400


class TestUploadAPI:

    async def _get_project_id(self, client: AsyncClient) -> str:
        resp = await client.get(f"{V1}/projects?page_size=1")
        items = resp.json()["data"]["items"]
        return items[0]["id"] if items else ""

    async def test_upload_text(self, authed_client: AsyncClient):
        pid = await self._get_project_id(authed_client)
        if not pid:
            pytest.skip("No project available")

        content = "测试文本内容\n用于上传测试".encode("utf-8")
        resp = await authed_client.post(
            f"{V1}/upload",
            data={"project_id": pid},
            files={"file": ("test.txt", io.BytesIO(content), "text/plain")},
        )
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["file_type"] == "text"

    async def test_upload_rejects_bad_type(self, authed_client: AsyncClient):
        pid = await self._get_project_id(authed_client)
        if not pid:
            pytest.skip("No project available")

        resp = await authed_client.post(
            f"{V1}/upload",
            data={"project_id": pid},
            files={"file": ("bad.exe", io.BytesIO(b"binary"), "application/octet-stream")},
        )
        assert resp.json()["code"] == 40010


class TestHealthAndAuth:

    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["status"] == "healthy"

    async def test_no_auth_rejected(self, client: AsyncClient):
        resp = await client.get(f"{V1}/projects")
        assert resp.status_code == 401  # missing auth header

    async def test_bad_token_rejected(self, client: AsyncClient):
        resp = await client.get(
            f"{V1}/projects",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert resp.json()["code"] == 40100