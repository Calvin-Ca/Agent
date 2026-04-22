"""Tests for report service via RESTful API."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

V1 = "/api/v1"


@pytest.mark.asyncio
async def test_list_reports_empty(authed_client: AsyncClient):
    resp = await authed_client.get(f"{V1}/reports")
    body = resp.json()
    assert body["code"] == 0
    assert "items" in body["data"]
    assert "total" in body["data"]


@pytest.mark.asyncio
async def test_get_nonexistent_report(authed_client: AsyncClient):
    resp = await authed_client.get(f"{V1}/reports/nonexistent-id")
    assert resp.json()["code"] == 40400


@pytest.mark.asyncio
async def test_list_reports_with_project_filter(authed_client: AsyncClient):
    resp = await authed_client.get(f"{V1}/reports", params={"project_id": "some-project-id"})
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["total"] == 0
