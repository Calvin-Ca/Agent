"""Product-facing V1 API router."""

from fastapi import APIRouter

from app.api_routes.v1.auth import router as auth_router
from app.api_routes.v1.chat import router as chat_router
from app.api_routes.v1.documents import router as documents_router
from app.api_routes.v1.progress import router as progress_router
from app.api_routes.v1.projects import router as projects_router
from app.api_routes.v1.reports import router as reports_router

v1_router = APIRouter()

v1_router.include_router(auth_router)
v1_router.include_router(chat_router)
v1_router.include_router(projects_router)
v1_router.include_router(progress_router)
v1_router.include_router(reports_router)
v1_router.include_router(documents_router)
