"""Structure tests for the slim product API surface."""

from __future__ import annotations

from fastapi.routing import APIRoute
from httpx import AsyncClient

from app.main import app

V1 = "/api/v1"


class TestRouteShape:

    def test_product_routes_only_expose_auth_and_chat(self):
        paths = {
            route.path
            for route in app.routes
            if isinstance(route, APIRoute)
        }

        assert f"{V1}/auth/register" in paths
        assert f"{V1}/auth/login" in paths
        assert f"{V1}/auth/me" in paths
        assert f"{V1}/chat" in paths
        assert f"{V1}/projects" not in paths
        assert f"{V1}/reports" not in paths
        assert f"{V1}/progress" not in paths
        assert f"{V1}/upload" not in paths


class TestHealthAndAuth:

    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["status"] == "healthy"

    async def test_legacy_product_routes_are_gone(self, client: AsyncClient):
        for path in ("projects", "reports", "progress", "upload"):
            resp = await client.get(f"{V1}/{path}")
            assert resp.status_code == 404

    async def test_bad_token_rejected(self, client: AsyncClient):
        resp = await client.get(
            f"{V1}/auth/me",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert resp.json()["code"] == 40100
