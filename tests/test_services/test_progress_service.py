"""Tests for progress service via RESTful API."""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

V1 = "/api/v1"


@pytest.fixture
async def project_id(authed_client: AsyncClient) -> str:
    """Create a project and return its ID for progress tests."""
    resp = await authed_client.post(f"{V1}/projects", json={
        "name": "进度测试项目",
        "code": "PROG-TEST",
    })
    return resp.json()["data"]["id"]


@pytest.mark.asyncio
async def test_record_progress(authed_client: AsyncClient, project_id: str):
    resp = await authed_client.post(f"{V1}/progress", json={
        "project_id": project_id,
        "record_date": date.today().isoformat(),
        "overall_progress": 35.0,
        "milestone": "基础开挖完成",
        "description": "完成了基础开挖工作",
        "blockers": "",
        "next_steps": "开始基础浇筑",
    })
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["overall_progress"] == 35.0
    assert body["data"]["milestone"] == "基础开挖完成"


@pytest.mark.asyncio
async def test_list_progress(authed_client: AsyncClient, project_id: str):
    # Record some progress first
    await authed_client.post(f"{V1}/progress", json={
        "project_id": project_id,
        "record_date": date.today().isoformat(),
        "overall_progress": 40.0,
    })

    resp = await authed_client.get(f"{V1}/progress", params={"project_id": project_id})
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["total"] >= 1
    assert len(body["data"]["items"]) >= 1


@pytest.mark.asyncio
async def test_list_progress_nonexistent_project(authed_client: AsyncClient):
    resp = await authed_client.get(f"{V1}/progress", params={"project_id": "nonexistent"})
    assert resp.json()["code"] == 40400
