"""Product-facing V1 API router.

Only two route groups:
- /auth   — authentication (register, login, me)
- /agent  — unified streaming agent endpoint
"""

from fastapi import APIRouter

from app.api_routes.v1.auth import router as auth_router
from app.api_routes.v1.agent import router as agent_router

v1_router = APIRouter()

v1_router.include_router(auth_router)
v1_router.include_router(agent_router)
