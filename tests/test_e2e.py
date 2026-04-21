from __future__ import annotations

from fastapi.routing import APIRoute

from app.main import app


def test_new_root_routes_exist():
    paths = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
    }

    assert "/health" in paths
    assert "/chat" in paths
    assert "/stream" in paths
    assert "/api/v1/chat" in paths
    assert "/api/v1/auth/login" in paths
