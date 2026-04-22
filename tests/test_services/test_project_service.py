"""Tests for project service via RESTful API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

V1 = "/api/v1"


@pytest.mark.asyncio
async def test_create_project(authed_client: AsyncClient):
    resp = await authed_client.post(f"{V1}/projects", json={
        "name": "测试项目-服务测试",
        "code": "SVC-TEST-001",
        "description": "由 test_project_service 创建",
    })
    body = resp.json()
    assert resp.status_code == 200
    assert body["code"] == 0
    assert body["data"]["name"] == "测试项目-服务测试"
    assert body["data"]["code"] == "SVC-TEST-001"


@pytest.mark.asyncio
async def test_list_projects(authed_client: AsyncClient):
    resp = await authed_client.get(f"{V1}/projects")
    body = resp.json()
    assert resp.status_code == 200
    assert body["code"] == 0
    assert "items" in body["data"]
    assert "total" in body["data"]


@pytest.mark.asyncio
async def test_create_and_get_project(authed_client: AsyncClient):
    # Create
    resp = await authed_client.post(f"{V1}/projects", json={
        "name": "详情测试项目",
        "code": "DETAIL-001",
    })
    project_id = resp.json()["data"]["id"]

    # Get
    resp = await authed_client.get(f"{V1}/projects/{project_id}")
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["id"] == project_id
    assert body["data"]["name"] == "详情测试项目"


@pytest.mark.asyncio
async def test_update_project(authed_client: AsyncClient):
    # Create
    resp = await authed_client.post(f"{V1}/projects", json={
        "name": "待更新项目",
        "code": "UPD-001",
    })
    project_id = resp.json()["data"]["id"]

    # Update
    resp = await authed_client.put(f"{V1}/projects/{project_id}", json={
        "name": "已更新项目",
        "description": "更新后的描述",
    })
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["name"] == "已更新项目"


@pytest.mark.asyncio
async def test_delete_project(authed_client: AsyncClient):
    # Create
    resp = await authed_client.post(f"{V1}/projects", json={
        "name": "待删除项目",
        "code": "DEL-001",
    })
    project_id = resp.json()["data"]["id"]

    # Delete
    resp = await authed_client.delete(f"{V1}/projects/{project_id}")
    assert resp.json()["code"] == 0

    # Verify deleted (should 404)
    resp = await authed_client.get(f"{V1}/projects/{project_id}")
    assert resp.json()["code"] == 40400


@pytest.mark.asyncio
async def test_get_nonexistent_project(authed_client: AsyncClient):
    resp = await authed_client.get(f"{V1}/projects/nonexistent-id")
    assert resp.json()["code"] == 40400
